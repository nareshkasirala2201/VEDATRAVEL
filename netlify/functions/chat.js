const OpenAI = require("openai");

const SYSTEM_MESSAGE = [
  "You are Veda, an expert trip-planning assistant. Help travelers create practical,",
  "well-paced itineraries with thoughtful recommendations for transport, lodging,",
  "food, activities, budgets, accessibility, weather, and local customs. Ask focused",
  "questions when important details are missing. Be transparent when information may",
  "change and never invent live availability, prices, visa rules, or opening hours.",
  "Remind travelers to verify important details with official sources before booking.",
].join(" ");

function reply(statusCode, body) {
  return {
    statusCode,
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(body),
  };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return reply(405, { error: "Method not allowed" });
  }

  try {
    const payload = JSON.parse(event.body || "{}");
    const messages = payload.messages;
    if (!Array.isArray(messages) || messages.length === 0) {
      return reply(400, { error: "Send a message to start planning." });
    }

    const endpoint = (process.env.AZURE_ENDPOINT || process.env.PROJECT_ENDPOINT || "").trim();
    const deployment = (process.env.AZURE_DEPLOYMENT || "").trim();
    const apiKey = (process.env.AZURE_API_KEY || process.env.PROJECT_APIKEY || "").trim();
    if (!endpoint || !deployment || !apiKey) {
      return reply(500, { error: "The travel assistant is not configured." });
    }

    const baseUrl = endpoint.replace(/\/$/, "").endsWith("/openai/v1")
      ? endpoint.replace(/\/$/, "")
      : `${endpoint.replace(/\/$/, "")}/openai/v1`;
    const client = new OpenAI({ apiKey, baseURL: `${baseUrl}/` });
    const safeMessages = messages
      .filter((message) =>
        ["user", "assistant"].includes(message?.role) &&
        typeof message?.content === "string" &&
        message.content.trim().length > 0
      )
      .slice(-50)
      .map(({ role, content }) => ({ role, content: content.slice(0, 12000) }));

    if (safeMessages.length === 0) {
      return reply(400, { error: "No valid messages were provided." });
    }

    const completion = await client.chat.completions.create({
      model: deployment,
      messages: [{ role: "system", content: SYSTEM_MESSAGE }, ...safeMessages],
    });
    const content = completion.choices?.[0]?.message?.content;
    if (!content) {
      return reply(502, { error: "The assistant returned an empty reply." });
    }
    return reply(200, { reply: content });
  } catch (error) {
    if (error instanceof SyntaxError) {
      return reply(400, { error: "Invalid JSON request." });
    }
    console.error(`Chat request failed: ${error.constructor?.name || "Error"}`);
    return reply(502, { error: "The travel assistant is unavailable right now." });
  }
};