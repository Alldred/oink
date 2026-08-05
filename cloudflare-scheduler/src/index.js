import { triggerBuild } from "./trigger.js";

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(triggerBuild(env));
  },

  async fetch(_request, env) {
    try {
      return await triggerBuild(env);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return new Response(`Failed to trigger Oink build: ${message}`, {
        status: 502,
      });
    }
  },
};
