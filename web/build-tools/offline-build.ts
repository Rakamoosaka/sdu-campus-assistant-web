import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import type { Plugin } from "vite";

export function offlineBuild(): Plugin {
  return {
    name: "campus-offline-shell",
    apply: "build",
    generateBundle: {
      order: "post",
      handler(_, bundle) {
        const worker = readFileSync(
          new URL("./offline-worker.js", import.meta.url),
          "utf8",
        );
        const index = bundle["index.html"];
        if (index?.type !== "asset")
          this.error("Offline shell requires index.html.");
        const files = Object.keys(bundle)
          .sort()
          .map((file) => "/" + file);
        const version = createHash("sha256")
          .update(JSON.stringify(files))
          .update(index.source)
          .update(worker)
          .digest("hex")
          .slice(0, 16);
        this.emitFile({
          type: "asset",
          fileName: "offline-worker.js",
          source: `const SHELL_CACHE = "sdu-map-shell-${version}";\nconst SHELL_FILES = ${JSON.stringify(files)};\n${worker}`,
        });
      },
    },
  };
}
