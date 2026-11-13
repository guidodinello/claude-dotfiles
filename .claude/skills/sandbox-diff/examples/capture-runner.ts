// Skeleton: a fail-closed stub for the vendor client, applied in the process that runs the flow.
// Allowlisted reads stay real, listed sends are captured and printed, every other method throws.
// Wire it into the app's own bootstrap (get the client instance from the DI container, then call
// installCaptureStub before invoking the unit under test). It covers this process only: stop or
// prove safe every worker, scheduler or container that could also run the code.
// Also point the vendor base URL at a dead host (http://127.0.0.1:9) for this process.

export type Captured = { method: string; summary: unknown };

type Methods = Record<string, unknown>;

export interface StubOptions {
  reads: ReadonlySet<string>;
  captures: Record<string, (...args: unknown[]) => { summary: unknown; result: unknown }>;
  internal?: ReadonlySet<string>;
}

function methodNames(instance: object): Set<string> {
  const names = new Set<string>();
  for (let proto: object | null = instance; proto && proto !== Object.prototype; proto = Object.getPrototypeOf(proto)) {
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === 'constructor') continue;
      const descriptor = Object.getOwnPropertyDescriptor(proto, name);
      if (descriptor && typeof descriptor.value === 'function') names.add(name);
    }
  }
  return names;
}

export function installCaptureStub(client: object, options: StubOptions): Captured[] {
  const captured: Captured[] = [];
  const target = client as Methods;
  for (const name of methodNames(client)) {
    if (options.internal?.has(name) || options.reads.has(name)) continue;
    const capture = options.captures[name];
    target[name] = capture
      ? async (...args: unknown[]) => {
          const { summary, result } = capture(...args);
          captured.push({ method: name, summary });
          return result;
        }
      : async () => {
          throw new Error(`harness: vendor ${name} blocked`);
        };
  }
  return captured;
}

export async function assertStubBlocks(client: object, unlistedMethod: string): Promise<void> {
  const fn = (client as Methods)[unlistedMethod];
  if (typeof fn !== 'function') throw new Error(`self-test: ${unlistedMethod} is not a method`);
  try {
    await (fn as () => Promise<unknown>).call(client);
  } catch (error) {
    if (error instanceof Error && error.message.startsWith('harness:')) return;
    throw error;
  }
  throw new Error(`self-test: ${unlistedMethod} did not throw; the stub fails open`);
}

// Example wiring (replace with the app's bootstrap and real method names):
//
// const client = app.get(VendorClient);
// const captured = installCaptureStub(client, {
//   reads: new Set(['getRecord', 'listRecords']),
//   captures: {
//     sendEmail: (_to, body) => ({ summary: { subject: (body as { subject?: string }).subject }, result: {} }),
//     sendSms: (to) => ({ summary: { to }, result: { id: 'harness' } }),
//   },
//   internal: new Set(['authenticate']),
// });
// await assertStubBlocks(client, 'deleteRecord');
// await app.get(UnitUnderTest).execute();
// console.log(`HARNESS_CAPTURED ${JSON.stringify(captured)}`);
