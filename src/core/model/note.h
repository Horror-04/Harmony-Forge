#pragma once

#include <string>
#include <vector>

namespace hf::core {

/// Single MIDI note. Ticks use 480 PPQ.
struct Note {
  int pitch = 60;        ///< 0..127
  int start_tick = 0;    ///< >= 0
  int duration_ticks = 480;  ///< > 0
  int velocity = 100;    ///< 1..127
};

enum class TrackType { Chords, Melody, Bass, Arpeggio, CounterMelody, Drums };

struct Track {
  TrackType type = TrackType::Melody;
  int channel = 0;  ///< 0..15
  std::vector<Note> notes;
};

struct Pattern {
  int ticks_per_beat = 480;
  int beats_per_bar = 4;
  std::vector<Track> tracks;
};

struct ChordSymbol {
  int root = 60;  ///< MIDI pitch class anchor (0..127, class = root % 12)
  std::string type = "maj";
  int inversion = 0;
  std::vector<int> tension;
};

using ChordProgression = std::vector<ChordSymbol>;

}  // namespace hf::core
