#include <catch2/catch_test_macros.hpp>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/music/chord_detect.h"
#include "core/music/key_detect.h"
#include "core/music/voice_leading.h"

namespace {

hf::core::Pattern make_c_major_material() {
  // C emphasized by duration (C total 1920 vs 480 each for the rest).
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes.push_back(hf::core::Note{60, 0, 960, 100});
  t.notes.push_back(hf::core::Note{64, 960, 480, 90});
  t.notes.push_back(hf::core::Note{67, 1440, 480, 90});
  t.notes.push_back(hf::core::Note{72, 1920, 960, 100});
  t.notes.push_back(hf::core::Note{62, 2880, 480, 90});
  t.notes.push_back(hf::core::Note{65, 3360, 480, 90});
  t.notes.push_back(hf::core::Note{69, 3840, 480, 90});
  t.notes.push_back(hf::core::Note{71, 4320, 480, 90});
  p.tracks.push_back(t);
  return p;
}

hf::core::Pattern make_a_minor_material() {
  // A emphasized by duration (A total 1920 vs 480 each for the rest).
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes.push_back(hf::core::Note{57, 0, 960, 100});
  t.notes.push_back(hf::core::Note{60, 960, 480, 90});
  t.notes.push_back(hf::core::Note{64, 1440, 480, 90});
  t.notes.push_back(hf::core::Note{69, 1920, 960, 100});
  t.notes.push_back(hf::core::Note{62, 2880, 480, 90});
  t.notes.push_back(hf::core::Note{67, 3360, 480, 90});
  t.notes.push_back(hf::core::Note{71, 3840, 480, 90});
  p.tracks.push_back(t);
  return p;
}

}  // namespace

TEST_CASE("detect_key finds C major", "[analysis][key]") {
  const hf::music::KeyEstimate est = hf::music::detect_key(make_c_major_material());
  CHECK(est.tonic % 12 == 0);
  CHECK(est.scale == "major");
  CHECK(est.confidence > 0.9f);
}

TEST_CASE("detect_key finds A minor", "[analysis][key]") {
  const hf::music::KeyEstimate est = hf::music::detect_key(make_a_minor_material());
  CHECK(est.tonic % 12 == 9);
  CHECK(est.scale == "natural_minor");
  CHECK(est.confidence > 0.9f);
}

TEST_CASE("detect_key is safe on empty/chromatic input", "[analysis][key]") {
  const hf::music::KeyEstimate empty = hf::music::detect_key(hf::core::Pattern{});
  CHECK(empty.confidence == 0.0f);

  hf::core::Pattern chromatic;
  hf::core::Track t;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});
  t.notes.push_back(hf::core::Note{61, 480, 480, 100});
  t.notes.push_back(hf::core::Note{62, 960, 480, 100});
  t.notes.push_back(hf::core::Note{63, 1440, 480, 100});
  chromatic.tracks.push_back(t);
  const hf::music::KeyEstimate est = hf::music::detect_key(chromatic);
  CHECK(est.confidence < 0.9f);  // never fully confident on a cluster
}

TEST_CASE("recognize_chord triads and sevenths", "[analysis][chord]") {
  auto c = hf::music::recognize_chord({60, 64, 67});
  CHECK(c.root % 12 == 0);
  CHECK(c.type == "maj");

  auto a = hf::music::recognize_chord({57, 60, 64});
  CHECK(a.root % 12 == 9);
  CHECK(a.type == "min");

  auto g7 = hf::music::recognize_chord({55, 59, 62, 65});
  CHECK(g7.root % 12 == 7);
  CHECK(g7.type == "7");

  auto cmaj7 = hf::music::recognize_chord({60, 64, 67, 71});
  CHECK(cmaj7.root % 12 == 0);
  CHECK(cmaj7.type == "maj7");

  auto ddim = hf::music::recognize_chord({62, 65, 68});
  CHECK(ddim.root % 12 == 2);
  CHECK(ddim.type == "dim");
}

TEST_CASE("recognize_chord bass disambiguates C6 vs Am7", "[analysis][chord]") {
  // Same pitch-class set {0,4,7,9}: bass decides the root.
  auto am7 = hf::music::recognize_chord({57, 60, 64, 67});
  CHECK(am7.root % 12 == 9);
  CHECK(am7.type == "m7");

  auto c6 = hf::music::recognize_chord({60, 64, 67, 69});
  CHECK(c6.root % 12 == 0);
  CHECK(c6.type == "6");
}

TEST_CASE("recognize_chord unknown input is safe", "[analysis][chord]") {
  const auto cluster = hf::music::recognize_chord({60, 61});
  CHECK(cluster.type == "unknown");
  const auto none = hf::music::recognize_chord({});
  CHECK(none.type == "unknown");
}

TEST_CASE("validate_voice_leading flags parallel fifths", "[analysis][voice]") {
  hf::core::Pattern p;
  hf::core::Track upper;
  upper.type = hf::core::TrackType::Melody;
  upper.notes.push_back(hf::core::Note{60, 0, 480, 100});
  upper.notes.push_back(hf::core::Note{62, 480, 480, 100});
  hf::core::Track lower;
  lower.type = hf::core::TrackType::Chords;
  lower.notes.push_back(hf::core::Note{67, 0, 480, 100});
  lower.notes.push_back(hf::core::Note{69, 480, 480, 100});
  p.tracks.push_back(upper);
  p.tracks.push_back(lower);

  const hf::music::VoiceReport r =
      hf::music::validate_voice_leading(p, hf::core::ChordProgression{});
  CHECK(r.parallel_fifths == 1);
  CHECK(r.parallel_octaves == 0);
}

TEST_CASE("validate_voice_leading flags parallel octaves", "[analysis][voice]") {
  hf::core::Pattern p;
  hf::core::Track upper;
  upper.notes.push_back(hf::core::Note{72, 0, 480, 100});
  upper.notes.push_back(hf::core::Note{74, 480, 480, 100});
  hf::core::Track lower;
  lower.notes.push_back(hf::core::Note{60, 0, 480, 100});
  lower.notes.push_back(hf::core::Note{62, 480, 480, 100});
  p.tracks.push_back(upper);
  p.tracks.push_back(lower);

  const hf::music::VoiceReport r =
      hf::music::validate_voice_leading(p, hf::core::ChordProgression{});
  CHECK(r.parallel_octaves == 1);
  CHECK(r.parallel_fifths == 0);
}

TEST_CASE("validate_voice_leading clean contrary motion passes", "[analysis][voice]") {
  hf::core::Pattern p;
  hf::core::Track upper;
  upper.notes.push_back(hf::core::Note{60, 0, 480, 100});
  upper.notes.push_back(hf::core::Note{62, 480, 480, 100});
  hf::core::Track lower;
  lower.notes.push_back(hf::core::Note{67, 0, 480, 100});
  lower.notes.push_back(hf::core::Note{65, 480, 480, 100});
  p.tracks.push_back(upper);
  p.tracks.push_back(lower);

  const hf::music::VoiceReport r =
      hf::music::validate_voice_leading(p, hf::core::ChordProgression{});
  CHECK(r.parallel_fifths == 0);
  CHECK(r.parallel_octaves == 0);
  CHECK(r.range_violations == 0);
  CHECK(r.strong_beat_dissonances == 0);
}

TEST_CASE("validate_voice_leading flags range violations", "[analysis][voice]") {
  hf::core::Pattern p;
  hf::core::Track bass;
  bass.type = hf::core::TrackType::Bass;
  bass.notes.push_back(hf::core::Note{80, 0, 480, 100});  // way above C3
  p.tracks.push_back(bass);

  const hf::music::VoiceReport r =
      hf::music::validate_voice_leading(p, hf::core::ChordProgression{});
  CHECK(r.range_violations == 1);
}

TEST_CASE("validate_voice_leading flags strong-beat dissonance", "[analysis][voice]") {
  hf::core::ChordProgression chords;
  chords.push_back(hf::core::ChordSymbol{60, "maj"});

  hf::core::Pattern bad;
  hf::core::Track mel;
  mel.type = hf::core::TrackType::Melody;
  mel.notes.push_back(hf::core::Note{61, 0, 480, 100});  // C# vs C major, beat 1
  bad.tracks.push_back(mel);
  const hf::music::VoiceReport rbad = hf::music::validate_voice_leading(bad, chords);
  CHECK(rbad.strong_beat_dissonances == 1);

  hf::core::Pattern good;
  hf::core::Track mel2;
  mel2.type = hf::core::TrackType::Melody;
  mel2.notes.push_back(hf::core::Note{60, 0, 480, 100});  // root, consonant
  good.tracks.push_back(mel2);
  const hf::music::VoiceReport rgood = hf::music::validate_voice_leading(good, chords);
  CHECK(rgood.strong_beat_dissonances == 0);
}

TEST_CASE("validate_voice_leading empty pattern is clean", "[analysis][voice]") {
  const hf::music::VoiceReport r =
      hf::music::validate_voice_leading(hf::core::Pattern{}, hf::core::ChordProgression{});
  CHECK(r.parallel_fifths == 0);
  CHECK(r.parallel_octaves == 0);
  CHECK(r.range_violations == 0);
  CHECK(r.strong_beat_dissonances == 0);
}
