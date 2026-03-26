import { FormEvent, useEffect, useMemo, useState } from 'react';
import { terminalService } from '../api';

type Provider = 'codex' | 'gemini' | 'ollama';

interface TerminalRun {
  id: string;
  provider: Provider;
  prompt: string;
  model?: string;
  ok: boolean;
  returnCode: number;
  durationMs: number;
  timedOut: boolean;
  stdout: string;
  stderr: string;
}

const asObject = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const asText = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

const asNumber = (value: unknown, fallback = 0): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback;

const asBool = (value: unknown, fallback = false): boolean =>
  typeof value === 'boolean' ? value : fallback;

export function Terminal() {
  const [provider, setProvider] = useState<Provider>('ollama');
  const [ollamaModel, setOllamaModel] = useState('llama3.1:8b');
  const [timeoutSeconds, setTimeoutSeconds] = useState(180);
  const [prompt, setPrompt] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<TerminalRun[]>([]);

  const [providerAvailability, setProviderAvailability] = useState<Record<Provider, boolean>>({
    codex: false,
    gemini: false,
    ollama: false,
  });
  const [allowedOllamaModels, setAllowedOllamaModels] = useState<string[]>([
    'qwen2.5-coder:7b',
    'llama3.1:8b',
    'gemma:7b',
  ]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const payload = await terminalService.getProviders();
        if (!mounted) {
          return;
        }
        const providers = asObject(payload.providers);
        setProviderAvailability({
          codex: asBool(asObject(providers.codex).available),
          gemini: asBool(asObject(providers.gemini).available),
          ollama: asBool(asObject(providers.ollama).available),
        });
        const ollama = asObject(providers.ollama);
        const models = asArray(ollama.allowed_models)
          .map((entry) => asText(entry))
          .filter((entry) => entry.length > 0);
        if (models.length > 0) {
          setAllowedOllamaModels(models);
          const suggested = asText(ollama.default_model, models[0]);
          setOllamaModel(models.includes(suggested) ? suggested : models[0]);
        }

        const logsPayload = await terminalService.getLogs(20);
        const logs = asArray(asObject(logsPayload).logs)
          .map((entry) => asObject(entry))
          .map((row) => {
            const providerText = asText(row.provider, 'ollama');
            const selectedProvider: Provider =
              providerText === 'codex' || providerText === 'gemini' || providerText === 'ollama'
                ? providerText
                : 'ollama';
            return {
              id: `log-${asNumber(row.ts, Date.now())}-${Math.random()}`,
              provider: selectedProvider,
              prompt: asText(row.prompt_preview),
              model: asText(row.model) || undefined,
              ok: asNumber(row.return_code, 1) === 0 && !asBool(row.timed_out, false),
              returnCode: asNumber(row.return_code, 1),
              durationMs: asNumber(row.duration_ms, 0),
              timedOut: asBool(row.timed_out, false),
              stdout: asText(row.stdout_preview),
              stderr: asText(row.stderr_preview),
            } satisfies TerminalRun;
          });
        if (logs.length > 0) {
          setRuns(logs);
        }
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : 'Failed to load terminal providers.');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const canRun = useMemo(() => {
    if (running || prompt.trim().length === 0) {
      return false;
    }
    return providerAvailability[provider] ?? false;
  }, [provider, providerAvailability, prompt, running]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canRun) {
      return;
    }

    const trimmed = prompt.trim();
    setRunning(true);
    setError(null);
    try {
      const payload = await terminalService.execute({
        provider,
        prompt: trimmed,
        model: provider === 'ollama' ? ollamaModel : undefined,
        timeout_seconds: timeoutSeconds,
      });
      const stdout = asText(payload.stdout);
      const stderr = asText(payload.stderr);
      const next: TerminalRun = {
        id: `${Date.now()}-${Math.random()}`,
        provider,
        prompt: trimmed,
        model: asText(payload.model) || undefined,
        ok: asBool(payload.ok),
        returnCode: asNumber(payload.return_code, 1),
        durationMs: asNumber(payload.duration_ms, 0),
        timedOut: asBool(payload.timed_out),
        stdout,
        stderr,
      };
      setRuns((previous) => [next, ...previous].slice(0, 30));
      setPrompt('');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Execution failed.');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-sm font-semibold text-slate-100">LLM Terminal</h2>
        <p className="mt-1 text-xs text-slate-400">
          Send prompts to local CLI providers from Kai. Ollama models are restricted to approved local models.
        </p>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <form className="space-y-3" onSubmit={onSubmit}>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="space-y-1 text-xs text-slate-300">
              <span className="font-medium text-slate-200">Provider</span>
              <select
                value={provider}
                onChange={(event) => setProvider(event.target.value as Provider)}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100 outline-none ring-cyan-500/30 focus:ring"
              >
                <option value="ollama">ollama</option>
                <option value="gemini">gemini</option>
                <option value="codex">codex</option>
              </select>
            </label>
            <label className="space-y-1 text-xs text-slate-300">
              <span className="font-medium text-slate-200">Ollama Model</span>
              <select
                value={ollamaModel}
                onChange={(event) => setOllamaModel(event.target.value)}
                disabled={provider !== 'ollama'}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100 outline-none ring-cyan-500/30 focus:ring disabled:opacity-50"
              >
                {allowedOllamaModels.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-xs text-slate-300">
              <span className="font-medium text-slate-200">Timeout (seconds)</span>
              <input
                type="number"
                min={5}
                max={600}
                value={timeoutSeconds}
                onChange={(event) => setTimeoutSeconds(Number(event.target.value) || 180)}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100 outline-none ring-cyan-500/30 focus:ring"
              />
            </label>
          </div>

          <label className="space-y-1 text-xs text-slate-300">
            <span className="font-medium text-slate-200">Prompt</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={5}
              placeholder="Ask about Kai architecture, workflows, code paths, or operations..."
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/30 focus:ring"
            />
          </label>

          {error ? <p className="text-xs text-rose-300">{error}</p> : null}

          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-400">
              Availability: codex {providerAvailability.codex ? 'online' : 'offline'} · gemini{' '}
              {providerAvailability.gemini ? 'online' : 'offline'} · ollama{' '}
              {providerAvailability.ollama ? 'online' : 'offline'}
            </p>
            <button
              type="submit"
              disabled={!canRun}
              className="rounded-md border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {running ? 'Running…' : 'Run Prompt'}
            </button>
          </div>
        </form>
      </section>

      <section className="space-y-3">
        {runs.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">
            No terminal runs yet.
          </div>
        ) : null}
        {runs.map((run) => (
          <article key={run.id} className="rounded-xl border border-slate-800 bg-slate-900/60">
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-4 py-2 text-xs">
              <div className="flex items-center gap-2 text-slate-300">
                <span className="rounded bg-slate-800 px-2 py-1 font-medium text-slate-200">{run.provider}</span>
                {run.model ? <span className="text-slate-400">{run.model}</span> : null}
                <span className={run.ok ? 'text-emerald-300' : 'text-rose-300'}>
                  {run.ok ? 'ok' : `exit ${run.returnCode}`}
                </span>
                {run.timedOut ? <span className="text-amber-300">timed out</span> : null}
              </div>
              <span className="text-slate-500">{run.durationMs} ms</span>
            </header>
            <div className="space-y-3 p-4">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Prompt</p>
                <pre className="whitespace-pre-wrap rounded-md border border-slate-800 bg-slate-950 p-3 text-xs text-slate-200">
                  {run.prompt}
                </pre>
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Output</p>
                <pre className="whitespace-pre-wrap rounded-md border border-slate-800 bg-black p-3 text-xs text-emerald-200">
                  {run.stdout || '(no stdout)'}
                </pre>
              </div>
              {run.stderr ? (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Errors</p>
                  <pre className="whitespace-pre-wrap rounded-md border border-slate-800 bg-black p-3 text-xs text-rose-200">
                    {run.stderr}
                  </pre>
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
