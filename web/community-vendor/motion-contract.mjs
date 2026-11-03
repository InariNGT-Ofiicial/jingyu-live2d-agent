/**
 * Model-agnostic motion contracts.
 * Behavior planning speaks in semantic control IDs, never Cubism parameter IDs.
 *
 * v2（PR #10 review fix）：上一版只有 supported/approximate/unsupported 与
 * {controls, weight, source}，既表达不了「未知能力」（文档要求 fail-closed 的 unknown），
 * 也无法降级到既有 WriteIntent 契约（缺 priority / phase / blend / owner）。
 * v2 补齐这些字段，并新增 `motion-intent.ts` 的 `lowerFrameToIntents` 作为语义层→
 * 既有 intent 契约的唯一降级路径——语义层永远不直接写模型参数。
 *
 * 兼容性：`MOTION_CONTRACT_VERSION` 参与 profile 校验，v2 与 v1 profile 不互通。
 */


/**
 * 契约版本。
 *
 * v3 相对 v2：新增 torso.contraction / arm.*.inward / leg.*.inward|bend 七个通道——
 * 它们是「害羞式保护姿态」的表达前提（收肩、双臂内收、腿部并拢）。
 * 注意：**通道存在不等于模型支持**，是否可写由 CapabilityProfile 的 status 决定，
 * 判不出来的通道必须是 unknown（fail-closed），不得默认 supported。
 */
export const MOTION_CONTRACT_VERSION = 3         ;

/**
 * 标准语义控制（归一化口径，默认 [-1, 1]）。
 *
 * 说明（对齐 docs/MOTION_ENGINE_AIRI_IMPLEMENTATION_GUIDE.md §3.1）：
 * - `face.blink` / `body.breathing` 是低优先级连续层，必须是可表达的语义控制；
 * - 手部姿势（hand.*.pose）是**资产**不是数值控制：它由 `MotionAssetCapability`
 *   的 `kind: 'pose'` 表达，避免把分类值塞进 [min,max] 数值区间。
 */















/** 标准语义控制 ID 列表（校验用，避免各处再抄一份）。 */
export const SEMANTIC_CONTROL_IDS = Object.freeze([
  'head.yaw',
  'head.pitch',
  'head.roll',
  'torso.lean',
  'torso.sway',
  'gaze.x',
  'gaze.y',
  'arm.left.raise',
  'arm.left.extend',
  'arm.left.inward',
  'arm.right.raise',
  'arm.right.extend',
  'arm.right.inward',
  'leg.left.inward',
  'leg.left.bend',
  'leg.right.inward',
  'leg.right.bend',
  'torso.contraction',
  'face.blink',
  'body.breathing',
]                                                );

/**
 * 适配器扩展通道：必须带 `ext.` 前缀，避免和标准语义通道混淆。
 * 标准通道增删属于契约变更（要升 contractVersion），扩展通道不需要。
 */



/**
 * 能力状态。`unknown` 是**合法且 fail-closed** 的状态：
 * 适配器无法确认某个通道能否安全写入时，必须报 unknown，而不是猜 supported。
 */




/** 写入相位：pre = 在 physics 之前（输入层），post = 在 physics 之后（姿态骨/眼球）。 */


/**
 * intent 优先级档位。与 `packages/core/src/action-chain.ts` 的 `ACT_PRIORITY_RANK`
 * （BACKGROUND=10 / NORMAL=50 / FORCE=90）以及 ownership spec 的 `intent.priority`
 * **同值同语义**——不允许出现第四套优先级词汇。
 */
export const SEMANTIC_PRIORITIES = Object.freeze([10, 50, 90]         );


/**
 * 来源秩，与 `docs/Ownership-Invariants.md` INV-6 的 source 秩同一份
 * （physics 是最终裁决者、不是生产者，所以不在此表）。
 */
export const SEMANTIC_SOURCE_RANK = Object.freeze({
  continuous: 1,
  ambient: 1,
  motion: 2,
  keyframes: 3,
  pose: 4,
  gaze: 5,
  limb: 6,
}         );















                                               
                                                           
























/**
 * G1 已实现的语义帧：planner（G2）产出 `SemanticMotionPlan` 后降级成本类型，
 * 再由 `lowerFrameToIntents()` 变成既有 `WriteIntent`。字段全部可选，缺省值见实现。
 */

                               




                  

                      

                             

                                                          

                                  





















export function isFiniteRange(min        , max        , neutral        )          {
  return Number.isFinite(min) && Number.isFinite(max) &&
    Number.isFinite(neutral) && min < max && neutral >= min && neutral <= max;
}

/** 标准 id 或 `ext.` 扩展 id。 */
export function isSemanticControlId(id        )                             {
  return (SEMANTIC_CONTROL_IDS                     ).includes(id) || id.startsWith('ext.');
}

export function isSemanticPriority(value        )                            {
  return (SEMANTIC_PRIORITIES                     ).includes(value);
}

export function isSemanticSource(value        )                          {
  return Object.prototype.hasOwnProperty.call(SEMANTIC_SOURCE_RANK, value);
}
