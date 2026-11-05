import base64, io, json, logging, re

import config

log = logging.getLogger("careerlens")


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "doc"


def extract_json(text: str) -> dict:
    """Pull the first balanced JSON object out of an LLM reply (tolerates prose and ``` fences)."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON in model output")


def to_float(s):
    m = re.search(r"\d+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


def image_to_b64(img, max_side: int = 1568, fmt: str = "PNG") -> str:
    img = img.convert("RGB")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)))
    buf = io.BytesIO()
    img.save(buf, format=fmt, **({"quality": 85} if fmt == "JPEG" else {}))
    return base64.b64encode(buf.getvalue()).decode()


def ocr_text(img) -> str:
    """Raw OCR text for RAG. Returns '' if Tesseract is not installed."""
    try:
        import pytesseract
        return pytesseract.image_to_string(img)
    except Exception as e:  # missing binary, etc.
        log.warning("OCR unavailable: %s", e)
        return ""


def llm_complete(prompt: str, system: str = "", images=None, max_tokens: int = 2000) -> str:
    """One entry point for text / vision LLM calls. Images require the anthropic provider."""
    if config.LLM_PROVIDER == "groq":
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        if images:   # OpenAI-style multimodal message; Groq allows ~5 images, ~4 MB each
            content = [{"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + image_to_b64(im, 1280, "JPEG")}} for im in images[:5]]
            content.append({"type": "text", "text": prompt})
        else:
            content = prompt
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": content}]
        r = client.chat.completions.create(
            model=config.GROQ_VISION_MODEL if images else config.GROQ_MODEL,
            messages=msgs, max_tokens=max_tokens, temperature=0)
        text = r.choices[0].message.content or ""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()   # drop reasoning blocks
    import anthropic
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example)")
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": image_to_b64(im)}} for im in (images or [])]
    content.append({"type": "text", "text": prompt})
    msg = client.messages.create(model=config.VLM_MODEL, max_tokens=max_tokens, system=system,
                                 messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if b.type == "text")
