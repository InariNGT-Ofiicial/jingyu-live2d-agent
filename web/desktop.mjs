// Desktop companion page: the same model and driver as the dashboard stage,
// but with no chrome, a transparent background and no renderer registration
// (exports and job dispatch stay with the dashboard window).
import {MotionEngine} from './engine.mjs';

const canvas = document.getElementById('pet-canvas');
const fail = message => {
  document.body.dataset.error = message;
  try { window.webkit?.messageHandlers?.pet?.postMessage({error: message}); } catch {}
};

if (!window.PIXI?.live2d?.Live2DModel || !window.Live2DCubismCore) {
  fail('本地 Live2D 运行库未能加载');
} else {
  boot().catch(error => fail(error.message || String(error)));
}

async function boot() {
  const profile = await (await fetch('/data/model-profile.json')).json();
  PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);
  const app = new PIXI.Application({
    view: canvas,
    width: Math.max(1, innerWidth),
    height: Math.max(1, innerHeight),
    backgroundAlpha: 0,
    antialias: true,
    autoDensity: true,
    resolution: Math.min(devicePixelRatio || 1, 2),
    powerPreference: 'high-performance'
  });
  const model = await PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json', {autoInteract: false, autoUpdate: true, motionPreload: 'NONE'});
  app.stage.addChild(model);

  const engine = new MotionEngine(model.internalModel.coreModel, profile, () => {});
  model.internalModel.eyeBlink = undefined;
  model.internalModel.breath = undefined;
  model.internalModel.updateFocus = () => {};
  let lastTick = performance.now();
  model.internalModel.updateNaturalMovements = () => {
    const now = performance.now();
    engine.tick(now - lastTick);
    lastTick = now;
  };

  const fit = () => {
    const width = Math.max(1, innerWidth), height = Math.max(1, innerHeight);
    app.renderer.resize(width, height);
    const scale = Math.min(width * 0.96 / model.internalModel.originalWidth, height * 0.98 / model.internalModel.originalHeight);
    model.scale.set(scale);
    model.anchor.set(0.5, 1);          // stand on the bottom edge
    model.position.set(width / 2, height);
  };
  fit();
  new ResizeObserver(fit).observe(document.documentElement);

  // Mirror dashboard playback: the bridge broadcasts to every event listener,
  // so the pet animates whenever a web-backend plan runs.
  const events = new EventSource('/api/events?after=0');
  events.addEventListener('execute', message => {
    const job = JSON.parse(message.data);
    if (job.backend !== 'web' || !['queued', 'playing'].includes(job.status) || !job.compiled) return;
    if (engine.job?.id === job.id) return;
    try { engine.start(job); } catch {}
  });
  events.addEventListener('stop', () => engine.stop());

  // Double-click asks the bridge for a random built-in demo.
  canvas.addEventListener('dblclick', async () => {
    try {
      const demos = await (await fetch('/api/demos')).json();
      const names = Object.keys(demos);
      if (!names.length) return;
      const name = names[Math.floor(Math.random() * names.length)];
      await fetch('/api/demo', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, backend: 'web'})
      });
    } catch {}
  });

  window.webkit?.messageHandlers?.pet?.postMessage({ready: true});
}