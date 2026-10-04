# VECTOR's designed voices

Original synthetic voices, designed from text with Qwen3-TTS-12Hz-1.7B-VoiceDesign (Apache-2.0); no one's recording was used. Each `vector-ref-*.wav` is the single reference the Base model speaks every line from, so the voice stays the same from sentence to sentence. Pick one with `qwen.ref_audio` in `../voice.json`.

| File | Description given to the designer | Seed | Median pitch |
|------|-----------------------------------|------|--------------|
| `vector-ref-A.wav` (default) | An older English gentleman in his sixties with a bright, prim and precise voice, crisp diction and quiet authority; cheerful, sing-song and delighted, like a very polite, very old caretaker who loves his job. Clear, warm and a little formal. | 27 | ~126 Hz |
| `vector-ref-B.wav` | A mature male voice in refined Received Pronunciation, gently high and bright, chipper and sing-song, crisp clipped diction, an air of ancient authority and quiet amusement. | 27 | ~125 Hz, the most lilting |
| `vector-ref-C.wav` | The same description as B. | 3 | ~168 Hz, brighter |

Every reference speaks: "Hello, and welcome. I am the caretaker, and everything here is running exactly as it should. Protocol is wise, and I am simply delighted to see you." That text is `qwen.ref_text`.

A third description ("a precise elderly British voice, light and tenor ...") came out at about 250 Hz, which isn't an older man, so it was dropped. To design another voice, run the VoiceDesign model with a new description and a fixed seed, check the pitch, save it here, and point `ref_audio` at it. Never use a recording of a real person, or of a game or film character, as a reference.
