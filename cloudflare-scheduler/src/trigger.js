/**
 * Dispatch the Oink dashboard build workflow via the GitHub API.
 *
 * @param {{ GITHUB_TOKEN: string }} env
 * @param {typeof fetch} [fetchFn]
 * @returns {Promise<Response>}
 */
export async function triggerBuild(env, fetchFn = fetch) {
  if (!env.GITHUB_TOKEN) {
    throw new Error("GITHUB_TOKEN secret is not configured");
  }

  const response = await fetchFn(
    "https://api.github.com/repos/Alldred/oink/actions/workflows/build-dashboard.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "oink-cloudflare-scheduler",
      },
      body: JSON.stringify({
        ref: "main",
      }),
    },
  );

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub returned ${response.status}: ${body}`);
  }

  return new Response("Oink build triggered", { status: 200 });
}
