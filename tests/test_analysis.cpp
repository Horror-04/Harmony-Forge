#include <catch2/catch_test_macros.hpp>

#include "constraints.h"
#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/music/chord_detect.h"
#include "core/music/key_detect.h"
#include "core/music/voice_leading.h"
#include "ranking.h"

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

TEST_CASE("drums-only pattern is analysis-clean", "[analysis][drums]") {
  // Drum pitches are an unpitched map: parallel motion, strong-beat clusters
  // and odd pitches here must all be ignored by pitched analysis.
  hf::core::Pattern p;
  hf::core::Track d1;
  d1.type = hf::core::TrackType::Drums;
  d1.notes.push_back(hf::core::Note{61, 0, 120, 100});
  d1.notes.push_back(hf::core::Note{62, 480, 120, 100});
  hf::core::Track d2;
  d2.type = hf::core::TrackType::Drums;
  d2.notes.push_back(hf::core::Note{68, 0, 120, 100});
  d2.notes.push_back(hf::core::Note{69, 480, 120, 100});
  p.tracks.push_back(d1);
  p.tracks.push_back(d2);

  hf::core::ChordProgression chords;
  chords.push_back(hf::core::ChordSymbol{60, "maj"});
  const hf::music::VoiceReport r = hf::music::validate_voice_leading(p, chords);
  CHECK(r.parallel_fifths == 0);
  CHECK(r.parallel_octaves == 0);
  CHECK(r.range_violations == 0);
  CHECK(r.strong_beat_dissonances == 0);

  const hf::music::KeyEstimate est = hf::music::detect_key(p);
  CHECK(est.tonic == 60);
  CHECK(est.scale == "major");
  CHECK(est.confidence == 0.0f);
}

TEST_CASE("drums do not skew pitched analysis", "[analysis][drums]") {
  hf::core::ChordProgression chords;
  chords.push_back(hf::core::ChordSymbol{60, "maj"});
  chords.push_back(hf::core::ChordSymbol{60, "maj"});
  chords.push_back(hf::core::ChordSymbol{60, "maj"});

  const hf::core::Pattern pitched = make_c_major_material();
  const hf::music::KeyEstimate key_plain = hf::music::detect_key(pitched);
  const hf::music::VoiceReport voice_plain =
      hf::music::validate_voice_leading(pitched, chords);

  hf::core::Pattern mixed = pitched;
  hf::core::Track drums;
  drums.type = hf::core::TrackType::Drums;
  drums.notes.push_back(hf::core::Note{61, 0, 120, 110});    // hostile hit: C#
  drums.notes.push_back(hf::core::Note{55, 0, 120, 100});    // parallel-motion pair
  drums.notes.push_back(hf::core::Note{57, 960, 120, 100});  // ...into a fifth
  mixed.tracks.push_back(drums);

  const hf::music::KeyEstimate key_mixed = hf::music::detect_key(mixed);
  CHECK(key_mixed.tonic == key_plain.tonic);
  CHECK(key_mixed.scale == key_plain.scale);
  CHECK(key_mixed.confidence == key_plain.confidence);

  const hf::music::VoiceReport voice_mixed =
      hf::music::validate_voice_leading(mixed, chords);
  CHECK(voice_mixed.parallel_fifths == voice_plain.parallel_fifths);
  CHECK(voice_mixed.parallel_octaves == voice_plain.parallel_octaves);
  CHECK(voice_mixed.range_violations == voice_plain.range_violations);
  CHECK(voice_mixed.strong_beat_dissonances == voice_plain.strong_beat_dissonances);
}

TEST_CASE("recognize_chord clamps out-of-range roots", "[analysis][chord]") {
  const auto empty = hf::music::recognize_chord({});
  CHECK(empty.root == 60);
  CHECK(empty.type == "unknown");

  const auto oor = hf::music::recognize_chord({-5, 200});
  CHECK(oor.root == 60);
  CHECK(oor.type == "unknown");

  const auto single_oor = hf::music::recognize_chord({200});
  CHECK(single_oor.root == 60);
  CHECK(single_oor.type == "unknown");

  // In-range pitches keep current behavior: out-of-range extras are ignored.
  const auto with_extra = hf::music::recognize_chord({60, 64, 67, 200});
  CHECK(with_extra.root % 12 == 0);
  CHECK(with_extra.type == "maj");
}

TEST_CASE("strong-beat is start_tick % 480 == 0 in audit, resolve and scorer",
          "[analysis][voice][phase2]") {
  // Phase 2 Task 1 (A): single strong-beat definition shared by
  // validate_voice_leading, resolve_harmonic_conflicts and strict_compliance.
  // F (65) is in C major but a minor 2nd above E, so it rubs C maj only on
  // strong beats. Beats 0..3 (ticks 0/480/960/1440) must flag identically.
  hf::core::ChordProgression chords;
  chords.push_back(hf::core::ChordSymbol{60, "maj"});

  auto one_note = [](int pitch, int start) {
    hf::core::Pattern p;
    p.ticks_per_beat = 480;
    p.beats_per_bar = 4;
    hf::core::Track t;
    t.type = hf::core::TrackType::Melody;
    t.notes.push_back(hf::core::Note{pitch, start, 480, 100});
    p.tracks.push_back(t);
    return p;
  };

  for (int start : {0, 480, 960, 1440}) {
    const auto p = one_note(65, start);
    CHECK(hf::music::validate_voice_leading(p, chords).strong_beat_dissonances == 1);
    auto q = one_note(65, start);
    hf::infer::resolve_harmonic_conflicts(q, chords);
    CHECK(q.tracks[0].notes[0].pitch == 64);  // nearest chord tone (E, down 1)
    CHECK(hf::infer::strict_compliance(p, chords, 60, "major") == 0.0f);
  }

  // Weak-beat tension is invisible to all three (policy: preserved).
  const auto w = one_note(65, 240);
  CHECK(hf::music::validate_voice_leading(w, chords).strong_beat_dissonances == 0);
  auto wq = one_note(65, 240);
  hf::infer::resolve_harmonic_conflicts(wq, chords);
  CHECK(wq.tracks[0].notes[0].pitch == 65);
  CHECK(hf::infer::strict_compliance(w, chords, 60, "major") == 1.0f);

  // Past the progression end all three agree it is safe (no chord to judge).
  const auto past = one_note(65, 2400);
  CHECK(hf::music::validate_voice_leading(past, chords).strong_beat_dissonances == 0);
  auto pastq = one_note(65, 2400);
  hf::infer::resolve_harmonic_conflicts(pastq, chords);
  CHECK(pastq.tracks[0].notes[0].pitch == 65);
  CHECK(hf::infer::strict_compliance(past, chords, 60, "major") == 1.0f);
}
