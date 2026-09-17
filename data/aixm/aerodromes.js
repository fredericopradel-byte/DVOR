(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};

  function build(data) {
    const runwayDirectionsById = new Map((data.runwayDirections || []).map(item => [item.id, item]));
    const pointsByDirection = new Map();

    (data.runwayPoints || []).forEach(point => {
      if (!modules.core.finitePosition(point) || !['THR', 'DISTHR'].includes(point.role)) return;
      const list = pointsByDirection.get(point.runwayId) || [];
      list.push(point);
      pointsByDirection.set(point.runwayId, list);
    });

    const thresholdsByDirection = new Map();
    runwayDirectionsById.forEach(direction => {
      const candidates = (pointsByDirection.get(direction.id) || [])
        .filter(point => !point.designator || point.designator === direction.designator)
        .sort((a, b) => {
          const role = { DISTHR: 0, THR: 1 };
          return (role[a.role] ?? 9) - (role[b.role] ?? 9) || String(b.validFrom || '').localeCompare(String(a.validFrom || ''));
        });
      if (candidates[0]) thresholdsByDirection.set(direction.id, candidates[0]);
    });

    return { runwayDirectionsById, thresholdsByDirection };
  }

  modules.aerodromes = { build };
})(window);
