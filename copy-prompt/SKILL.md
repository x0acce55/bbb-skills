---
name: copy-prompt
description: Copy a generated prompt (or any text the user will paste elsewhere) to the clipboard (pbcopy on macOS, clip.exe on Windows). Use whenever the user asks for a prompt, an improved prompt, or asks to copy text to their clipboard.
argument-hint: "path to a file, or leave empty to copy the most recent prompt"
---

Put the deliverable text on the user's clipboard so they can paste it directly
(usually into a claude.ai chat).

## Procedure

1. Identify the text: the prompt just generated, the file the user named, or —
   with no argument — the most recently generated prompt in this conversation
   (often already saved as `prompt-*.md` in an import staging directory).
2. If the text isn't already in a file, write it to one first (staging directory
   if one exists for this work, else the scratchpad). The file is the durable copy;
   the clipboard is volatile.
3. Copy, per OS:
   - macOS: `pbcopy < <file>`
   - Windows (Git Bash): `clip.exe < <file>`
   - Linux: `xclip -selection clipboard < <file>` or `wl-copy < <file>`, whichever
     is present; say which was used.
4. Verify without dumping the clipboard, and report "copied to clipboard (N bytes)":
   - macOS: `pbpaste | wc -c` and compare to the file's byte count.
   - Windows: `powershell.exe -command "(Get-Clipboard -Raw).Length"` and compare to
     the file's character count (`wc -m`) — clip.exe may add a trailing CRLF, so
     within a couple of characters is a pass.
   - Linux: `xclip -selection clipboard -o | wc -c` (or `wl-paste | wc -c`).

## Rules

- Copy exactly the paste-ready text — no surrounding markdown fences, no
  "---" delimiters used for display, no commentary.
- Still show or reference the prompt in the reply; never make the clipboard the
  only copy.
- Never pipe secrets or credential-bearing text to the clipboard.
- If the user asks for a prompt and this skill wasn't explicitly invoked, copy it
  anyway and mention that it's on the clipboard — that's the standing preference.
