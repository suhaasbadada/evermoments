export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function pingApi(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/ping`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Ping failed with status ${response.status}`);
  }

  const data = (await response.json()) as { message?: string };
  return data.message ?? "unknown";
}
