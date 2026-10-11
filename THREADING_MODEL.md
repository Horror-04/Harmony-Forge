# Threading Model

1. [DAW Audio Thread] (Real-Time Priority)
   - Executes `PluginProcessor::processBlock()`.
   - Reads pre-generated MIDI events from a Lock-Free Ring Buffer.
   - Outputs MIDI to DAW or feeds simple internal synth.
   - Read-only access to Playhead / Transport (BPM, position).

2. [GUI Thread] (Message Thread)
   - JUCE UI repaints, Piano Roll rendering, user inputs.
   - Pushes user intent (e.g., "Regenerate Bar 4") to Command Queue.

3. [Inference Background ThreadPool] (Worker Threads)
   - Long-running inference (ONNX Runtime).
   - Generates candidates, applies Music Theory Constraints.
   - Sends finished patterns back to GUI thread via AsyncUpdater/MessageManagerLock-safe queues.