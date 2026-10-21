// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Guard B12 (D-B12 entry condition, Sonnet's rule): headless bounds-dump
// guard for the S9.3 Editor extraction.
//
// Method: instantiate the REAL HarmonyForgeEditor headless (no peer, no
// window, no paint — paint is never called, no Image, no drawText), setSize
// at four window sizes, and dump every descendant component's bounds (and
// ONLY bounds). Expectations live FILE-BACKED in
// tests/golden/b12_editor_bounds.json (S4b precedent: no value-pinning
// literals in-test); ANY mismatch exits NON-ZERO. Because every run compares
// against the golden file, determinism is proven across processes on every
// invocation.
//
// Golden path idiom (same as the chordtrack/sampler pins): the absolute path
// comes from the HARMONY_FORGE_B12_BOUNDS compile definition (wired in
// tests/CMakeLists.txt); the relative fallback below only serves direct
// binary runs, which MUST run from the repo root — a missing file fails
// loudly (never skips).
//
// Regeneration: `--write [out-path]` rewrites the golden file from a live
// headless run (precedent: tools/update_golden_midi.py --write). Default
// out-path is the golden path above. The committed file must always equal a
// --write into a temp copy (byte-compare, proven per regeneration).
//
// If the editor cannot be instantiated headless (needs a peer/audio device,
// crashes in ctor/resized/teardown), this guard fails with the error
// evidence — the editor is NOT re-architected to make it pass.
//
// Deliberately NOT registered with catch_discover_tests (never in `ctest -N`;
// the counters it protects are unchanged by its existence — 221/221 in
// build-off/Debug, 254/254 in build-full/Release).
// CI integration is FUTURE WORK (S93-3 ruling).
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>

#include <cstdio>
#include <filesystem>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "audio/PluginEditor.h"
#include "audio/PluginProcessor.h"
#include "model_manifest.h"  // hf::infer::sha256_hex_text (vector-verified impl)

#ifndef HARMONY_FORGE_B12_BOUNDS
#define HARMONY_FORGE_B12_BOUNDS "tests/golden/b12_editor_bounds.json"
#endif

namespace {

// The golden doc line, byte-exact (the --write renderer below must emit the
// committed file byte-identically; this single string is the only copy).
const char* kGoldenDoc =
    "B12 editor-layout bounds pins (probe_b12_bounds guard, D-B12 entry "
    "condition). Per window size: expected descendant-component count, "
    "canonical dump byte count, and SHA256 of the canonical bounds-dump text "
    "(LF bytes). Captured 2026-10-21 headless (no peer, no paint) on the "
    "master tree at 0f131ba (Release build). Regenerate only via the probe "
    "--write mode; any byte change here must move the same bytes the guard "
    "asserts.";

// Size keys in fixed golden order (function, not a string table).
const char* size_key(int i) {
  if (i == 0) return "960x600";
  if (i == 1) return "1024x876";
  if (i == 2) return "1280x800";
  return "2048x1752";
}

struct Expect {
  int w = 0;
  int h = 0;
  int components = 0;
  size_t bytes = 0;
  std::string sha256;
};

// Minimal strict reader for the golden file (house shape: same as the
// sampler_wiring / chordtrack readers; R3: no JSON lib in C++. Quoted
// strings are parsed, so the double-quote is spelled 34, never as a char
// literal — otherwise the off-golden lint masker sees phantom strings.
// Every shape deviation returns false, never throws).
bool b12_is_ws(char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r'; }

bool b12_is_digit(char c) { return c >= '0' && c <= '9'; }

bool b12_is_hex(char c) {
  return b12_is_digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

std::string b12_read_file(const char* path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  std::ostringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

bool b12_key_colon(const std::string& text, size_t& pos, const char* key) {
  const std::string q = std::string(1, 34) + key + std::string(1, 34);
  const size_t at = text.find(q, pos);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  while (pos < text.size() && b12_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != ':') return false;
  ++pos;
  while (pos < text.size() && b12_is_ws(text[pos])) ++pos;
  return pos < text.size();
}

bool b12_parse_int(const std::string& text, size_t& pos, long& out) {
  while (pos < text.size() && b12_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || !b12_is_digit(text[pos])) return false;
  long v = 0;
  while (pos < text.size() && b12_is_digit(text[pos])) {
    v = v * 10 + (text[pos] - '0');
    if (v > 1000000000L) return false;
    ++pos;
  }
  out = v;
  return true;
}

bool b12_parse_quoted(const std::string& text, size_t& pos, std::string& out) {
  while (pos < text.size() && b12_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != 34) return false;
  ++pos;
  out.clear();
  while (pos < text.size() && text[pos] != 34) {
    const unsigned char c = static_cast<unsigned char>(text[pos]);
    if (c < 0x20 || c > 0x7e) return false;
    out.push_back(text[pos]);
    ++pos;
  }
  if (pos >= text.size()) return false;
  ++pos;
  return !out.empty();
}

bool b12_expect(const std::string& text, size_t& pos, char c) {
  while (pos < text.size() && b12_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != c) return false;
  ++pos;
  return true;
}

bool b12_parse_dims(const char* key, int& w, int& h) {
  const std::string k(key);
  const size_t x = k.find('x');
  if (x == std::string::npos) return false;
  long lw = 0, lh = 0;
  size_t pos = 0;
  if (!b12_parse_int(k, pos, lw)) return false;
  if (pos != x) return false;
  pos = x + 1;
  if (!b12_parse_int(k, pos, lh)) return false;
  if (pos != k.size() || lw <= 0 || lh <= 0) return false;
  w = static_cast<int>(lw);
  h = static_cast<int>(lh);
  return true;
}

// Reads the four ordered expectations; false on ANY shape deviation
// (missing file, missing key, wrong int, bad sha shape, ...).
bool b12_read_expectations(const char* path, std::vector<Expect>& out) {
  const std::string text = b12_read_file(path);
  if (text.empty()) return false;
  size_t pos = 0;
  if (!b12_key_colon(text, pos, "sizes")) return false;
  if (!b12_expect(text, pos, '{')) return false;
  out.clear();
  for (int i = 0; i < 4; ++i) {
    Expect e;
    if (!b12_parse_dims(size_key(i), e.w, e.h)) return false;
    if (!b12_key_colon(text, pos, size_key(i))) return false;
    if (!b12_expect(text, pos, '{')) return false;
    long comps = 0, bytes = 0;
    if (!b12_key_colon(text, pos, "components")) return false;
    if (!b12_parse_int(text, pos, comps)) return false;
    if (!b12_expect(text, pos, ',')) return false;
    if (!b12_key_colon(text, pos, "bytes")) return false;
    if (!b12_parse_int(text, pos, bytes)) return false;
    if (!b12_expect(text, pos, ',')) return false;
    if (!b12_key_colon(text, pos, "sha256")) return false;
    if (!b12_parse_quoted(text, pos, e.sha256)) return false;
    if (!b12_expect(text, pos, '}')) return false;
    e.components = static_cast<int>(comps);
    e.bytes = static_cast<size_t>(bytes);
    if (e.sha256.size() != 64) return false;
    for (char c : e.sha256)
      if (!b12_is_hex(c)) return false;
    out.push_back(e);
  }
  return out.size() == 4;
}

void dump_tree(const juce::Component* c, const std::string& path, int depth,
               std::ostringstream& out, int& count) {
  const auto b = c->getBounds();
  out << "d" << depth << " " << path << " [" << b.getX() << "," << b.getY()
      << "," << b.getWidth() << "," << b.getHeight() << "]\n";
  ++count;
  for (int i = 0; i < c->getNumChildComponents(); ++i)
    dump_tree(c->getChildComponent(i), path + "/" + std::to_string(i), depth + 1,
              out, count);
}

// Byte-exact golden renderer (must emit the committed file identically).
std::string b12_render_golden(const std::vector<std::string>& dumps,
                              const std::vector<int>& counts) {
  std::ostringstream o;
  o << "{\n";
  o << "  " << std::string(1, 34) << "doc" << std::string(1, 34) << ": "
    << std::string(1, 34) << kGoldenDoc << std::string(1, 34) << ",\n";
  o << "  " << std::string(1, 34) << "sizes" << std::string(1, 34) << ": {\n";
  for (int i = 0; i < 4; ++i) {
    o << "    " << std::string(1, 34) << size_key(i) << std::string(1, 34)
      << ": {" << std::string(1, 34) << "components" << std::string(1, 34)
      << ": " << counts[static_cast<size_t>(i)] << ", " << std::string(1, 34)
      << "bytes" << std::string(1, 34) << ": " << dumps[static_cast<size_t>(i)].size()
      << ", " << std::string(1, 34) << "sha256" << std::string(1, 34) << ": "
      << std::string(1, 34) << hf::infer::sha256_hex_text(dumps[static_cast<size_t>(i)])
      << std::string(1, 34) << "}";
    o << (i + 1 < 4 ? ",\n" : "\n");
  }
  o << "  }\n";
  o << "}\n";
  return o.str();
}

}  // namespace

int main(int argc, char** argv) {
  const bool write = argc > 1 && std::string(argv[1]) == "--write";
  const std::string golden_path =
      (write && argc > 2) ? argv[2] : HARMONY_FORGE_B12_BOUNDS;

  juce::ScopedJuceInitialiser_GUI juceInit;
  std::printf("[b12] juce-init ok\n");
  std::fflush(stdout);

  HarmonyForgeProcessor proc;
  std::printf("[b12] processor ok\n");
  std::fflush(stdout);

  auto editor = std::make_unique<HarmonyForgeEditor>(proc);
  const bool noPeer = (editor->getPeer() == nullptr);
  std::printf("[b12] editor-construct ok peer=%s\n", noPeer ? "null" : "NON-NULL");
  std::fflush(stdout);

  // Four canonical dumps (layout only — resized, never paint).
  std::vector<std::string> dumps;
  std::vector<int> counts;
  for (int i = 0; i < 4; ++i) {
    int w = 0, h = 0;
    if (!b12_parse_dims(size_key(i), w, h)) {
      std::printf("[b12] FAIL: bad size key\n");
      return 1;
    }
    editor->setSize(w, h);
    int n1 = 0, n2 = 0;
    std::ostringstream o1, o2;
    dump_tree(editor.get(), "root", 0, o1, n1);
    dump_tree(editor.get(), "root", 0, o2, n2);
    if (o1.str() != o2.str()) {
      std::printf("[b12] size %s determinism-twice: FAIL\n", size_key(i));
      return 1;
    }
    dumps.push_back(o1.str());
    counts.push_back(n1);
  }

  if (write) {
    const std::string golden = b12_render_golden(dumps, counts);
    std::ofstream f(golden_path, std::ios::binary | std::ios::trunc);
    if (!f) {
      std::printf("[b12] FAIL: cannot write %s\n", golden_path.c_str());
      return 1;
    }
    f << golden;
    f.close();
    if (!f) {
      std::printf("[b12] FAIL: write failed %s\n", golden_path.c_str());
      return 1;
    }
    std::printf("[b12] wrote %s (%zu bytes)\n", golden_path.c_str(), golden.size());
    return 0;
  }

  int failures = 0;
  const auto check = [&](bool ok, const char* what, const char* key) {
    std::printf("[b12] size %s pin-%s: %s\n", key, what, ok ? "PASS" : "FAIL");
    std::fflush(stdout);
    if (!ok) ++failures;
  };

  check(noPeer, "headless-no-peer", "all");
  std::vector<Expect> exp;
  const bool read_ok = b12_read_expectations(HARMONY_FORGE_B12_BOUNDS, exp);
  if (!read_ok)
    std::printf("[b12] FAIL: cannot read expectations from %s (run from the "
                "repo root, or configure with the absolute define)\n",
                HARMONY_FORGE_B12_BOUNDS);
  check(read_ok, "golden-readable", "all");
  check(exp.size() == 4, "four-sizes", "all");

  if (read_ok && exp.size() == 4) {
    for (int i = 0; i < 4; ++i) {
      const char* key = size_key(i);
      const Expect& e = exp[static_cast<size_t>(i)];
      const std::string& s = dumps[static_cast<size_t>(i)];
      const int n = counts[static_cast<size_t>(i)];
      check(n == e.components, "component-count", key);
      check(s.size() == e.bytes, "byte-count", key);
      // Hash via the inference lib's vector-verified sha256 (lowercase hex).
      const std::string got = hf::infer::sha256_hex_text(s);
      const bool hashOk = (got == e.sha256);
      if (!hashOk)
        std::printf("[b12] size %s sha256 mismatch (got %.16s...)\n", key,
                    got.c_str());
      check(hashOk, "sha256", key);
      std::printf("[b12] size %s: components=%d bytes=%zu\n", key, n, s.size());
      std::fflush(stdout);
    }
  }

  namespace fs = std::filesystem;
  // The diagnostic dumps go to a SCRATCH directory (`.superpowers/` is
  // git-ignored): they are throwaway output, NOT a durable record. The
  // durable record is the tracked golden `tests/golden/b12_editor_bounds.json`
  // plus its record in `tests/golden_manifest.json` - nothing here points at
  // a path that is not in this repository.
  // QUALIFICATION: that golden is the durable record of the LAST capture.
  // It was RE-CAPTURED on 2026-10-21 - the phase-B backlog's "OPEN FOLLOW-UP
  // (B12 bounds golden re-capture)" (docs/BACKLOG-phase-B.md, the B12 block)
  // is CLOSED: the pin now holds the MEASURED post-B2 descendant-component
  // count 139 at every window size (the ArrangeBar gained two widgets, and
  // JUCE's ComboBox installs an internal Label child - the count is a
  // measurement, never an arithmetic), together with the dump byte counts
  // and sha256s that go with it. The probe is neither ctest-registered nor
  // in CI, so a later layout change is caught by hand (RED until the next
  // re-capture), never by a gate.
  const fs::path outdir = ".superpowers/sdd-tmp/probe-b12-dumps";
  std::error_code ec;
  fs::create_directories(outdir, ec);
  for (int i = 0; i < 4; ++i) {
    const std::string name =
        std::string("bounds-") + size_key(i) + "-check.txt";
    std::ofstream f(outdir / name, std::ios::binary | std::ios::trunc);
    f << dumps[static_cast<size_t>(i)];
  }

  editor.reset();
  std::printf("[b12] editor-destroy ok\n");
  std::printf("[b12] %s (%d failures)\n", failures == 0 ? "ALL-PASS" : "FAILURES",
              failures);
  return failures == 0 ? 0 : 1;
}
