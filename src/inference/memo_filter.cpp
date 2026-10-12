// Runtime §10 memo-filter. See memo_filter.h for the exact policy.
// Pure C++20, no JUCE. Never throws (domain/file errors -> nullopt/no-op).
#include "memo_filter.h"

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <system_error>
#include <utility>

#include "core/serialization/tokenizer.h"

namespace hf::infer {
namespace {

constexpr int kWindow = 8;       // same window as evaluate.py / dataset.py
constexpr int kMinRun = 4;       // >= 4 consecutive memorized windows = copy
constexpr uint32_t kVersion = 1;
constexpr size_t kMaxWindows = 1 << 20;  // corrupt-size guard (~32 MB)

bool read_le(const std::vector<char>& buf, size_t& pos, uint32_t& v) noexcept {
  if (pos + 4 > buf.size()) return false;
  uint32_t x = 0;
  for (int i = 0; i < 4; ++i)
    x |= static_cast<uint32_t>(static_cast<unsigned char>(buf[pos + i])) << (8 * i);
  pos += 4;
  v = x;
  return true;
}

bool read_window(const std::vector<char>& buf, size_t& pos,
                 std::array<int32_t, 8>& w) noexcept {
  if (pos + 32 > buf.size()) return false;
  for (int i = 0; i < 8; ++i) {
    uint32_t x = 0;
    for (int b = 0; b < 4; ++b)
      x |= static_cast<uint32_t>(static_cast<unsigned char>(buf[pos + b])) << (8 * b);
    pos += 4;
    int32_t v = 0;
    std::memcpy(&v, &x, 4);
    w[static_cast<size_t>(i)] = v;
  }
  return true;
}

std::optional<MemoIndex> load_impl(const std::string& path) {
  if (path.empty()) return std::nullopt;
  std::error_code ec;
  const auto size = std::filesystem::file_size(std::filesystem::path(path), ec);
  if (ec || size < 12 || size > 12 + kMaxWindows * 32) return std::nullopt;
  std::ifstream f(std::filesystem::path(path), std::ios::binary);
  if (!f.good()) return std::nullopt;
  std::vector<char> buf(static_cast<size_t>(size));
  f.read(buf.data(), static_cast<std::streamsize>(buf.size()));
  if (!f || f.gcount() != static_cast<std::streamsize>(buf.size()))
    return std::nullopt;
  if (buf[0] != 'H' || buf[1] != 'F' || buf[2] != 'M' || buf[3] != 'I')
    return std::nullopt;
  size_t pos = 4;
  uint32_t version = 0, count = 0;
  if (!read_le(buf, pos, version) || version != kVersion) return std::nullopt;
  if (!read_le(buf, pos, count) || count > kMaxWindows) return std::nullopt;
  if (buf.size() != 12 + static_cast<size_t>(count) * 32) return std::nullopt;
  std::vector<std::array<int32_t, 8>> ws;
  ws.reserve(count);
  for (uint32_t i = 0; i < count; ++i) {
    std::array<int32_t, 8> w{};
    if (!read_window(buf, pos, w)) return std::nullopt;
    ws.push_back(w);
  }
  MemoIndex idx;
  idx.windows = std::move(ws);
  if (!std::is_sorted(idx.windows.begin(), idx.windows.end()))
    std::sort(idx.windows.begin(), idx.windows.end());
  idx.windows.erase(std::unique(idx.windows.begin(), idx.windows.end()),
                    idx.windows.end());
  return idx;
}

// Process-wide positive-hit cache (background threads only; misses are
// re-probed every call so a newly installed index is picked up).
std::mutex& cache_mutex() {
  static std::mutex m;
  return m;
}

std::map<std::string, std::shared_ptr<const MemoIndex>>& index_cache() {
  static std::map<std::string, std::shared_ptr<const MemoIndex>> c;
  return c;
}

std::string resolve_index_path(const std::string& model_path) {
  if (model_path.empty()) return std::string{};
  const std::filesystem::path mp(model_path);
  const std::filesystem::path parent = mp.parent_path();
  if (!parent.empty()) return (parent / "memo_index.bin").string();
  // F2: bare filename — no sibling to name, so read it as relative to the
  // working directory and probe the index there.
  std::error_code ec;
  const std::filesystem::path cwd = std::filesystem::current_path(ec);
  if (ec) return std::string{};
  return (cwd / "memo_index.bin").string();
}

// One-time stderr diagnostic for an unsatisfiable non-empty model path
// (background threads only; lock-free flag, no-throw C I/O).
void memo_index_missing_once(const std::string& model_path,
                             const std::string& resolved) noexcept {
  try {
    static std::atomic_flag warned;
    if (!warned.test_and_set(std::memory_order_relaxed)) {
      const std::string msg =
          "[harmony-forge] memo index unavailable for model '" + model_path +
          "' (tried '" + resolved +
          "'); runtime plagiarism filter (SPEC 10) inactive for this session.\n";
      std::fwrite(msg.c_str(), 1, msg.size(), stderr);
    }
  } catch (...) {
  }
}

}  // namespace

bool MemoIndex::contains(const std::array<int32_t, 8>& w) const noexcept {
  try {
    return std::binary_search(windows.begin(), windows.end(), w);
  } catch (...) {
    return false;
  }
}

MemoIndex make_memo_index(
    std::vector<std::array<int32_t, 8>> windows) noexcept {
  try {
    std::sort(windows.begin(), windows.end());
    windows.erase(std::unique(windows.begin(), windows.end()), windows.end());
    MemoIndex idx;
    idx.windows = std::move(windows);
    return idx;
  } catch (...) {
    return MemoIndex{};
  }
}

std::optional<MemoIndex> load_memo_index(const std::string& path) noexcept {
  try {
    return load_impl(path);
  } catch (...) {
    return std::nullopt;
  }
}

void apply_memo_filter(core::Pattern& p, const MemoIndex& idx) noexcept {
  try {
    if (idx.empty()) return;
    // Drumless view for the check; original drums reattached verbatim.
    core::Pattern drumless = p;
    drumless.tracks.erase(
        std::remove_if(drumless.tracks.begin(), drumless.tracks.end(),
                       [](const core::Track& t) {
                         return t.type == core::TrackType::Drums;
                       }),
        drumless.tracks.end());
    const std::vector<int> ids = hf::ser::encode_pattern(drumless);
    if (ids.size() < static_cast<size_t>(kWindow + kMinRun - 1)) return;
    // First window j ending a run of kMinRun consecutive memorized windows.
    size_t offending = 0;
    bool found = false;
    int run = 0;
    for (size_t k = 0; k + kWindow <= ids.size(); ++k) {
      std::array<int32_t, 8> w{};
      for (int i = 0; i < kWindow; ++i) w[static_cast<size_t>(i)] = ids[k + i];
      run = idx.contains(w) ? run + 1 : 0;
      if (run >= kMinRun) {
        offending = k;
        found = true;
        break;
      }
    }
    if (!found) return;  // clean: p untouched (bit-identical pass-through)
    // Cut BEFORE the completing token (last token of window `offending`),
    // repair to whole notes (same as evaluate.finalize).
    const size_t keep = offending + kWindow - 1;
    const size_t n = (keep >= 1) ? (keep - 1) / 6 : 0;
    std::vector<int> cut;
    cut.reserve(1 + n * 6);
    cut.push_back(static_cast<int>(n));
    for (size_t i = 1; i < 1 + n * 6 && i < ids.size(); ++i) cut.push_back(ids[i]);
    const auto decoded = hf::ser::decode_tokens(cut);
    if (!decoded) return;
    std::vector<core::Track> drums;
    for (const auto& t : p.tracks)
      if (t.type == core::TrackType::Drums) drums.push_back(t);
    p.tracks = decoded->tracks;
    p.tracks.insert(p.tracks.end(), drums.begin(), drums.end());
  } catch (...) {
    // Best effort: on unexpected failure prefer leaving `p` usable. Note
    // `p.tracks` is only assigned after a successful decode, so a throw
    // before that point leaves `p` untouched.
  }
}

std::string memo_index_path_for_model(const std::string& model_path) noexcept {
  try {
    return resolve_index_path(model_path);
  } catch (...) {
    return std::string{};
  }
}

void apply_memo_filter_for_model(core::Pattern& p,
                                 const std::string& model_path) noexcept {
  try {
    apply_memo_filter_for_model(p, model_path, !model_path.empty());
  } catch (...) {
  }
}

void apply_memo_filter_for_model(core::Pattern& p, const std::string& model_path,
                                 bool runner_involved) noexcept {
  try {
    // F1: the pure deterministic fallback (no runner, no model) is never
    // filtered, so its output stays bit-identical everywhere (tripwire).
    if (!runner_involved && model_path.empty()) return;
    // F1: a runner with no model file (test/override seam) can only probe
    // the working directory; F2: a bare filename resolves there too.
    std::string path;
    if (!model_path.empty())
      path = memo_index_path_for_model(model_path);
    else {
      std::error_code ec;
      const std::filesystem::path cwd = std::filesystem::current_path(ec);
      if (!ec) path = (cwd / "memo_index.bin").string();
    }
    if (path.empty()) return;
    std::shared_ptr<const MemoIndex> hit;
    {
      const std::lock_guard<std::mutex> lock(cache_mutex());
      const auto it = index_cache().find(path);
      if (it != index_cache().end()) hit = it->second;
    }
    if (!hit) {
      if (auto loaded = load_memo_index(path)) {
        hit = std::make_shared<const MemoIndex>(std::move(*loaded));
        const std::lock_guard<std::mutex> lock(cache_mutex());
        index_cache()[path] = hit;
      } else {
        // F2: unsatisfiable non-empty model path -> safe no-op + one-time
        // diagnostic (never on the audio thread; empty-path test seams
        // stay silent to keep test logs clean).
        if (!model_path.empty()) memo_index_missing_once(model_path, path);
        return;
      }
    }
    apply_memo_filter(p, *hit);
  } catch (...) {
  }
}

}  // namespace hf::infer
