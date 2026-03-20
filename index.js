import dotenv from "dotenv";

dotenv.config();

const CLAUDE_API_KEY = process.env.ANTHROPIC_API_KEY;
if (!CLAUDE_API_KEY) {
  console.error("ERROR: Set ANTHROPIC_API_KEY in .env");
  process.exit(1);
}

async function runClaudeCode() {
  const prompt = `You are a helpful code assistant. Write a JavaScript function that returns the first n Fibonacci numbers as an array.`;

  const body = {
    model: "claude-code-v1",
    prompt,
    max_tokens: 300,
    temperature: 0.2,
    top_p: 1,
    stop_sequences: ["\n\n"]
  };

  const res = await fetch("https://api.anthropic.com/v1/complete", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CLAUDE_API_KEY
    },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Claude API error ${res.status}: ${text}`);
  }

  const data = await res.json();
  console.log("=== Claude Code response ===");
  console.log(data.completion);
}

runClaudeCode().catch((err) => {
  console.error(err);
});
