# VN Background Generator

Auto-generate visual novel style backgrounds for SillyTavern using ComfyUI.

---

## WARNING

**This extension is vibe-coded.** It was hacked together quickly and may break, behave unexpectedly, or require manual fixes. If you prefer polished, well-tested software, this is not for you.

Use at your own risk.

---

## Credits

Based on [Image Gen Kazuma](https://github.com/Kazuma-Dev/Image-gen-kazuma) by Kazuma-Dev. The original extension provides a much more feature-rich and configurable ComfyUI integration for SillyTavern.

---

## What It Does

- Extracts scene information from your chat using an LLM (OpenAI-compatible API)
- Generates background prompts with danbooru-style tags
- Sends the prompt to ComfyUI to generate a background image
- Sets the generated image as your SillyTavern background

---

## Requirements

- **Illustrious XL models only** - The prompts and quality tags are optimized specifically for Illustrious/WAI models. Other model families will likely produce poor results.
- ComfyUI running with `--listen --enable-cors-header` flags
- An OpenAI-compatible API for scene extraction (can use local LLM)

---

## Installation

1. Launch ComfyUI with: `--listen --enable-cors-header`
2. In SillyTavern: Extensions -> Install Extension
3. Paste this repo URL
4. Refresh SillyTavern

---

## Configuration

1. **ComfyUI**: Enter your ComfyUI URL (default: `http://127.0.0.1:8188`) and click the test button
2. **Checkpoint**: Select an Illustrious-based model
3. **Scene Extraction API**: Configure an OpenAI-compatible endpoint, API key, and model for scene analysis
4. **LoRAs**: Optionally select up to 4 LoRAs

---

## Usage

- **Manual**: Click the panorama icon near the chat input
- **Auto**: Enable "Auto-generate on message" to generate after each AI response

---

## License

MIT License
