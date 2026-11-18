// The player asks for a choice only at a clip boundary.
export class MotionDirector {
 constructor(policy, now = () => performance.now()) {
  this.policy = policy;
  this.now = now;
  this.state = 'idle';
  this.mode = 'chat';
  this.lastInput = now();
  this.last = new Map();
  this.pending = null;
  this.cursor = {};
  this.current = null;
 }

 setState(state) {
  this.state = state;
  if (state === 'listening') this.touch();
 }
 touch() { this.lastInput = this.now(); }
 setMode(mode) {
  this.mode = mode === 'quiet' ? 'quiet' : 'chat';
  this.pending = null;
  this.touch();
 }
 cancel() { this.pending = null; this.state = 'idle'; this.touch(); }

 request(name, {explicit = false, priority = 1, ttl = 8000, turnId, covered = false} = {}) {
  const clip = this.policy.clips[name];
  if (!clip) return;
  const t = this.now();
  if (this.pending?.expires > t && this.pending.priority > priority) return;
  if (covered || name === this.current) {
   this.pending = null;
   return;
  }
  if (!explicit && t - (this.last.get(name) ?? -Infinity) < clip.cooldownMs) return;
  this.pending = {name, explicit, priority, expires: t + ttl, turnId};
 }

 next(ready = () => true) {
  const t = this.now();
  const quiet = this.mode === 'quiet' || t - this.lastInput >= this.policy.idleAfterMs;
  const state = quiet && this.state === 'idle' ? 'quiet' : this.state;
  const pools = this.policy.pools;
  const pool = pools[state] || pools.idle;
  let reason = state, name, turnId;
  const available = candidate => candidate !== this.current && ready(candidate);
  const cooled = candidate => t - (this.last.get(candidate) ?? -Infinity) >= this.policy.clips[candidate].cooldownMs;

  const p = this.pending;
  if (p && p.expires > t && (p.explicit || cooled(p.name))) {
   if (available(p.name)) {
    name = p.name;
    turnId = p.turnId;
    reason = p.explicit ? 'requested' : 'response';
   } else {
    reason = 'buffering-next';
   }
  }
  if (reason !== 'buffering-next' || !p?.explicit) this.pending = null;

  if (!name) {
   let index = this.cursor[state] || 0;
   for (let n = 0; n < pool.length; n++) {
    const candidate = pool[index++ % pool.length];
    if (cooled(candidate) && available(candidate)) { name = candidate; break; }
   }
   this.cursor[state] = index;
   // A depleted pool can borrow a quiet idle. Keep an expressive action on cooldown.
   const idles = quiet ? (pools.quiet || pools.idle) : pools.idle;
   name ??= idles.find(candidate => cooled(candidate) && available(candidate));
   name ??= ['front-breathe', 'h3-shoulders'].find(candidate => this.policy.clips[candidate] && available(candidate));
  }
  // Keep the last rendered frame while a different clip loads.
  if (!name) return null;
  this.current = name;
  this.last.set(name, t);
  return {name, reason, at: t, turnId};
 }
}
