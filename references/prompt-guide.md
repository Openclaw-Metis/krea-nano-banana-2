# Prompt Guide for Krea Nano Banana 2

## Basics

Nano Banana 2 is powered by Google Imagen and excels at photorealistic imagery. Write naturally in English with enough detail for the model to understand what you want.

A good prompt covers:
- **Subject**: what is in the image ("a young woman at a café", "a sunset over Shibuya crossing")
- **Style**: artistic direction ("photorealistic", "K-pop editorial", "cinematic", "fashion photography")
- **Lighting/mood**: atmosphere ("golden hour", "neon glow", "soft natural light", "studio lighting")
- **Composition**: framing ("close-up portrait", "full body shot", "wide angle", "over-the-shoulder")

## Prompt structure

Put the most important elements first. The model gives more weight to earlier tokens.

Pattern: `[subject], [style], [lighting], [details], [quality modifiers]`

## Examples

**K-pop style portrait**
`a young woman with long black hair and bangs, wearing a pastel oversized hoodie, K-pop idol aesthetic, soft studio lighting, clean background, editorial photography, highly detailed`

**Travel / food content**
`a bowl of ramen with soft-boiled egg and chashu pork, steam rising, izakaya setting, warm ambient lighting, food photography, shallow depth of field, appetizing`

**Street fashion**
`a stylish young woman in a plaid skirt and cropped jacket, walking through Harajuku, cherry blossoms in background, golden hour, street photography, candid, 8k`

**Lifestyle / café**
`a young woman sitting by a window in a minimalist café, reading a book, latte on table, soft diffused daylight, cozy atmosphere, lifestyle photography`

**Travel scenery**
`a young woman standing on a cliff overlooking the ocean, wind blowing her hair, dramatic sunset sky, cinematic wide shot, travel photography`

## Using reference images (imageUrls)

Nano Banana 2 supports multiple reference images via `--image-urls`. This is critical for character consistency (e.g., maintaining the same face across different scenes).

Tips for reference images:
- Use 1-3 clear, well-lit reference photos of the character
- Front-facing, neutral expression works best as a base reference
- The model will blend reference visuals with your text prompt
- More references = more consistent results but slightly less creative freedom

## Tips

- Nano Banana 2 excels at photorealistic output — lean into that strength
- For character consistency, always include reference images via `--image-urls`
- Quality modifiers like "highly detailed", "8k", "professional photography" help
- Avoid negative phrasing; describe what you want, not what you don't want
- For batch generation (`--batch-size 2-4`), each image will be a variation
- Use `4:5` aspect ratio for IG feed posts, `9:16` for stories/reels, `1:1` for square posts
