// Skeleton: a fail-closed stub for the vendor client, applied in the process that runs the flow.
// Allowlisted reads stay real, listed sends are captured and printed, every other method throws.
// Decision-only mode (recordBlocked): every blocked call is also recorded with a payload summary
// before it throws, so each version's decision is read from its attempted writes with zero
// sandbox writes. Run both base and PR with the same options. When the unit has no catch around a
// write and its decision continues past it, list that write in `simulate`: the call is recorded and
// returns a harness-built response (from real reads) instead of throwing. It never reaches the vendor.
// Wire it into the app's own bootstrap (get the client instance from the DI container, then call
// installCaptureStub before invoking the unit under test). It covers this process only: stop or
// prove safe every worker, scheduler or container that could also run the code.
// Also point the vendor base URL at a dead host (http://127.0.0.1:9) for this process.

export type Captured = { method: string; summary: unknown; blocked?: true; simulated?: true };

type Methods = Record<string, unknown>;

export interface StubOptions {
  reads: ReadonlySet<string>;
  captures: Record<string, (...args: unknown[]) => { summary: unknown; result: unknown }>;
  internal?: ReadonlySet<string>;
  recordBlocked?: (method: string, args: unknown[]) => unknown;
  simulate?: Record<
    string,
    (...args: unknown[]) => { summary: unknown; result: unknown } | Promise<{ summary: unknown; result: unknown }>
  >;
}

export function assertSandboxHost(baseUrl: string | undefined, sandboxHost: string): void {
  const host = baseUrl ? new URL(baseUrl).host : '(none)';
  console.error(`host: ${host}`);
  if (host !== sandboxHost) throw new Error(`harness: ${host} is not the sandbox host`);
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
    const simulated = options.simulate?.[name];
    if (simulated) {
      target[name] = async (...args: unknown[]) => {
        const { summary, result } = await simulated(...args);
        captured.push({ method: name, summary, blocked: true, simulated: true });
        return result;
      };
      continue;
    }
    target[name] = capture
      ? async (...args: unknown[]) => {
          const { summary, result } = capture(...args);
          captured.push({ method: name, summary });
          return result;
        }
      : async (...args: unknown[]) => {
          if (options.recordBlocked) {
            captured.push({ method: name, summary: options.recordBlocked(name, args), blocked: true });
          }
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

// Example wiring (replace with the app's bootstrap and real method names). With a DI framework,
// build the app context without starting HTTP or workers, e.g. in NestJS:
//   const app = await NestFactory.createApplicationContext(CliModule);
//   assertSandboxHost(process.env.VENDOR_API_BASE_URL, 'sandbox.vendor.example');
//   const client = app.get(VendorClient, { strict: false });
// If the runner imports a unit only in one mode, use a non-literal import specifier, or the
// type-check of the other mode fails on the missing file.
//
// const captured = installCaptureStub(client, {
//   reads: new Set(['getRecord', 'listRecords']),
//   captures: {
//     sendEmail: (_to, body) => ({ summary: { subject: (body as { subject?: string }).subject }, result: {} }),
//     sendSms: (to) => ({ summary: { to }, result: { id: 'harness' } }),
//   },
//   internal: new Set(['authenticate']),
//   // Unit has no catch around createRecord: answer from a real read of the destination definition.
//   simulate: {
//     createRecord: async (target, body) => ({ summary: { target }, result: buildFrom(await readDefinition(target), body) }),
//   },
//   // Decision-only: record which record each blocked write targeted (ids and tags, no payload values).
//   recordBlocked: (_method, args) => ({ target: args[0], tag: (args[1] as { externalId?: string })?.externalId }),
// });
// await assertStubBlocks(client, 'deleteRecord');
// captured.length = 0; // the self-test's own blocked call is recorded in decision-only mode
// await app.get(UnitUnderTest).execute();
// console.log(`HARNESS_CAPTURED ${JSON.stringify(captured)}`);
// await app.close();
