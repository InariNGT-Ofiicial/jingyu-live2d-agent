/**
 * 语义帧 → 既有 `WriteIntent` 契约的降级层（唯一映射路径）。
 *
 * 为什么必须有这一层：PR #10 评审的 P1 就是「语义层直接写参数 = 第二套仲裁」。
 * 这里把 `SemanticMotionFrame` 变成 `docs/Embodied-Behavior.md` 定义的 intent：
 *
 *   { id, source, priority(10/50/90), phase('pre'|'post'), params, runId? }
 *
 * 之后仍然由现有 ParamMixer / param-ownership 裁决，语义层不持有写权限。
 *
 * 契约对齐（不新增词汇）：
 * - `priority` 只允许 10/50/90，与 `action-chain.ts` 的 `ACT_PRIORITY_RANK` 同值；
 * - `source` 取自 INV-6 的 source 秩（continuous/ambient/motion/keyframes/pose/gaze/limb）；
 * - `phase` 与 INV-7 一致：物理根输入（AngleX、PositionX、LeanInput、Movement1、HipAngleX 等）
 *   **只能 pre**，这里对 post 写入直接 fail-closed 拒绝；
 * - `blend`（override/add，即 mixer.ts 的 BlendMode）暂不进 intent：intent 契约里没有
 *   这个字段，混合语义属于 M1-c 的 Mixer 接线，缺口记在文档里而不是偷偷加字段。
 */

import {
  SEMANTIC_SOURCE_RANK,
  isSemanticControlId,
  isSemanticPriority,
  isSemanticSource,





} from './motion-contract.mjs';

/**
 * 物理根输入：必须在 physics 之前写入（docs/Ownership-Invariants.md INV-7）。
 * 与 `tools/ownership-spec/reference.mjs` 的 `PRE_ONLY` 同一份名单。
 */
export const PRE_ONLY_PARAMS                      = new Set([
  'AngleX', 'AngleY', 'AngleZ',
  'PositionX', 'PositionY', 'PositionZ',
  'LeanInput', 'Movement1', 'Movement2', 'Movement3',
  'HipAngleX', 'HipAngleY', 'HipAngleZ',
]);

/** 语义控制 → 原生参数的绑定。模型差异（参数名/量程/缩放）只能出现在这里。 */


                            

                                             

                                                

                                                                  



                    



/** 与 `docs/Embodied-Behavior.md` 的 intent 形状一致；字段不多不少。 */




















/** 参数族默认相位：物理根输入 pre，其余（姿态骨/眼球/表情）post。 */
export function defaultPhaseForParam(paramId        )             {
  return PRE_ONLY_PARAMS.has(paramId) ? 'pre' : 'post';
}

/** 校验绑定表本身（Adapter 装配时调用一次，不进帧循环）。 */
export function validateChannelBindings(bindings         )                                    {
  const errors           = [];
  if (!Array.isArray(bindings)) return { ok: false, errors: ['bindings must be an array'] };
  const seen = new Set        ();
  for (const [index, raw] of bindings.entries()) {
    const binding = raw                  ;
    if (!binding || typeof binding !== 'object') { errors.push(`bindings[${index}] must be an object`); continue; }
    if (typeof binding.controlId !== 'string' || !isSemanticControlId(binding.controlId)) {
      errors.push(`bindings[${index}].controlId is not a semantic control id`);
    }
    if (typeof binding.paramId !== 'string' || !binding.paramId.trim()) errors.push(`bindings[${index}].paramId is required`);
    if (binding.phase !== undefined && binding.phase !== 'pre' && binding.phase !== 'post') errors.push(`bindings[${index}].phase is invalid`);
    if (binding.scale !== undefined && !Number.isFinite(binding.scale)) errors.push(`bindings[${index}].scale must be finite`);
    if (binding.offset !== undefined && !Number.isFinite(binding.offset)) errors.push(`bindings[${index}].offset must be finite`);
    if (binding.bounds !== undefined) {
      const bounds = binding.bounds;
      if (!Array.isArray(bounds) || bounds.length !== 2 || !Number.isFinite(bounds[0]) || !Number.isFinite(bounds[1]) || bounds[0] > bounds[1]) {
        errors.push(`bindings[${index}].bounds must be [min, max]`);
      }
    }
    if (binding.source !== undefined && !isSemanticSource(binding.source)) errors.push(`bindings[${index}].source is invalid`);
    if (typeof binding.controlId === 'string') {
      if (seen.has(binding.controlId)) errors.push(`duplicate binding: ${binding.controlId}`);
      seen.add(binding.controlId);
    }
  }
  return { ok: errors.length === 0, errors };
}

/**
 * 语义帧 → intents。纯函数、无副作用、可安全在 planner 线程/主线程调用。
 *
 * 拒绝原因（fail-closed，绝不静默丢控制）：
 * - `unknown-control`：不是标准语义 id 也没带 `ext.` 前缀；
 * - `unbound-control`：绑定表里没有这个控制（当前模型不支持 → 应该报 unsupported，不是猜）；
 * - `invalid-value`：非有限数；
 * - `invalid-binding`：绑定表里的 scale/offset 非法；
 * - `invalid-phase` / `pre-only-param`：INV-7 保护（物理根输入只能 pre）；
 * - `invalid-bounds`：绑定表 bounds 非法；
 * - `duplicate-param`：两个控制写同一个原生参数（会互相覆盖）；
 * - 帧级：`invalid-frame` / `invalid-priority` / `invalid-source`。
 */
export function lowerFrameToIntents(
  frame                                        ,
  bindings                            = [],
  options                        = {},
)              {
  const rejected                    = [];
  const warnings           = [];
  if (!frame || typeof frame !== 'object' || Array.isArray(frame)) {
    return { intents: [], rejected: [{ controlId: '*', reason: 'invalid-frame' }], warnings };
  }
  const priority         = frame.priority ?? 50;
  if (!isSemanticPriority(priority)) {
    return { intents: [], rejected: [{ controlId: '*', reason: 'invalid-priority' }], warnings };
  }
  const frameSource         = frame.source ?? 'motion';
  if (!isSemanticSource(frameSource)) {
    return { intents: [], rejected: [{ controlId: '*', reason: 'invalid-source' }], warnings };
  }

  const byControl = new Map                        ();
  for (const binding of Array.isArray(bindings) ? bindings : []) {
    if (binding && typeof binding.controlId === 'string') byControl.set(binding.controlId, binding);
  }

  const groups = new Map                                                                                                                   ();
  const usedParams = new Map                ();
  const controls = frame.controls && typeof frame.controls === 'object' && !Array.isArray(frame.controls) ? frame.controls : {};

  for (const rawId of Object.keys(controls)) {
    const controlId = rawId;
    if (!isSemanticControlId(controlId)) { rejected.push({ controlId, reason: 'unknown-control' }); continue; }
    const binding = byControl.get(controlId);
    if (!binding) { rejected.push({ controlId, reason: 'unbound-control' }); continue; }

    const value = (controls                           )[controlId];
    if (typeof value !== 'number' || !Number.isFinite(value)) { rejected.push({ controlId, reason: 'invalid-value' }); continue; }

    const scale = binding.scale ?? 1;
    const offset = binding.offset ?? 0;
    if (!Number.isFinite(scale) || !Number.isFinite(offset)) { rejected.push({ controlId, reason: 'invalid-binding' }); continue; }

    const phase = binding.phase ?? frame.phase ?? defaultPhaseForParam(binding.paramId);
    if (phase !== 'pre' && phase !== 'post') { rejected.push({ controlId, reason: 'invalid-phase' }); continue; }
    // INV-7：物理根输入只允许 pre；写成 post 等于让物理覆盖结果（白写），直接拒。
    if (phase === 'post' && PRE_ONLY_PARAMS.has(binding.paramId)) {
      rejected.push({ controlId, reason: 'pre-only-param' });
      continue;
    }

    let native = value * scale + offset;
    if (!Number.isFinite(native)) { rejected.push({ controlId, reason: 'non-finite-value' }); continue; }
    if (binding.bounds !== undefined) {
      const bounds = binding.bounds;
      if (!Array.isArray(bounds) || bounds.length !== 2 || !Number.isFinite(bounds[0]) || !Number.isFinite(bounds[1]) || bounds[0] > bounds[1]) {
        rejected.push({ controlId, reason: 'invalid-bounds' });
        continue;
      }
      native = Math.min(Number(bounds[1]), Math.max(Number(bounds[0]), native));
    }

    const takenBy = usedParams.get(binding.paramId);
    if (takenBy !== undefined && takenBy !== controlId) {
      rejected.push({ controlId, reason: 'duplicate-param:' + binding.paramId });
      continue;
    }
    usedParams.set(binding.paramId, controlId);

    const source = binding.source ?? (frameSource                  );
    if (!isSemanticSource(source)) { rejected.push({ controlId, reason: 'invalid-source' }); continue; }

    const key = source + '|' + priority + '|' + phase;
    let group = groups.get(key);
    if (!group) {
      group = { source, priority: priority                    , phase, params: {} };
      groups.set(key, group);
    }
    group.params[binding.paramId] = native;
  }

  const baseId = options.intentId || frame.decisionId || 'semantic';
  const ordered = [...groups.values()].sort((a, b) =>
    a.priority - b.priority ||
    SEMANTIC_SOURCE_RANK[a.source] - SEMANTIC_SOURCE_RANK[b.source] ||
    (a.phase === b.phase ? 0 : a.phase === 'pre' ? -1 : 1));
  const intents                = ordered.map((group, index) => {
    const intent              = {
      id: baseId + '#' + index,
      source: group.source,
      priority: group.priority,
      phase: group.phase,
      params: group.params,
    };
    if (frame.runId !== undefined) intent.runId = frame.runId;
    return intent;
  });
  if (intents.length === 0 && rejected.length === 0) warnings.push('empty-frame');
  return { intents, rejected, warnings };
}
