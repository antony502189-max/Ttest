# Evidence byte representations

`SHA256.json` records original Windows working-file bytes captured before commit.
Those original local output files remain retained. Git normalizes CRLF text to
LF when storing blobs, so some text hashes differ after cloning the repository.

Use **SHA256_GIT_BLOBS.json** to verify exact published repository artifact bytes
at source commit `5bc8ea9b950748a2ea6c45d6e3144ae4e0c7776f`. Read each file with
`git show <commit>:<path>` without shell text decoding/newline conversion, then
calculate SHA256. Binary image bytes are identical in both representations.
The original manifest is preserved; no previously published evidence is replaced.
