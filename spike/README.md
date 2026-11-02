# Spike code (1 Nov 2026)

Throwaway scripts from the SAM and length spike, kept so the work is not lost with a temp folder.
Written on 1 Nov 2026, inside the hackathon window.

- `sam/call.py`: upload a photo, call SAM 3.1, save the stream. `sam/decode.mjs`: decode masks with @meta-sam/parser.
- `len/lib.py`: SAM client with cache, length along the body (skeleton longest path), min-area-rect sides. `len/exp_*.py`: the experiments.
- The scripts have hard-coded absolute paths (a session temp folder, the main checkout `.env` and `pics/`). They do not run as they are. Slice 0 rewrites the useful parts as tested modules.
- Not kept: photos, masks, raw SAM output, the bundled Python packages.
