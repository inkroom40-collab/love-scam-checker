export default async function handler(req, res) {
  // Nur POST erlauben
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { imageUrl } = req.body;

    if (!imageUrl) {
      return res.status(400).json({ error: "imageUrl fehlt" });
    }

    const response = await fetch(
      `https://serpapi.com/search?engine=google_lens&url=${encodeURIComponent(
        imageUrl
      )}&api_key=${process.env.SERPAPI_KEY}`
    );

    const contentType = response.headers.get("content-type");

    // Sicherstellen, dass JSON zurückkommt
    if (!contentType || !contentType.includes("application/json")) {
      const text = await response.text();
      console.error("Nicht JSON:", text);
      return res.status(500).json({ error: "Ungültige API Antwort" });
    }

    const data = await response.json();

    // Nur relevante Daten zurückgeben
    const results = data.visual_matches || [];

    res.status(200).json({
      matches: results,
      count: results.length
    });

  } catch (error) {
    console.error("Server Fehler:", error);
    res.status(500).json({ error: "Server Fehler" });
  }
}
