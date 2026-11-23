export default {
  compose(compose: { services?: Record<string, { env_file?: string | string[] }> }) {
    const envFile = process.env.TRADELAB_RUNTIME_ENV_FILE;
    if (!envFile) return;

    const app = compose.services?.app;
    if (!app) throw new Error("TradeLab's app service is missing from Compose.");
    const files = app.env_file;
    app.env_file = [...(Array.isArray(files) ? files : files ? [files] : []), envFile];
  },
};
