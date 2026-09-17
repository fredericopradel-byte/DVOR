(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};

  function build(data, context) {
    const systemsByDirection = new Map();
    const visualAids = (data.visualGlideSlopeIndicators || []).map(item => {
      const direction = context.runwayDirectionsById.get(item.runwayDirectionId) || null;
      const threshold = context.thresholdsByDirection.get(item.runwayDirectionId) || null;
      const airport = modules.core.airportSummary(item.airport || direction && direction.airport);
      const system = {
        id: item.id,
        type: item.type || 'VGSI',
        side: item.side || '',
        slopeAngle: Number.isFinite(item.slopeAngle) ? Number(item.slopeAngle) : null,
        minimumEyeHeightOverThreshold: item.minimumEyeHeightOverThreshold || null,
        numberOfBoxes: Number.isFinite(item.numberOfBoxes) ? Number(item.numberOfBoxes) : null,
        runwayDirectionId: item.runwayDirectionId || '',
        runwayDirectionDesignator: item.runwayDirectionDesignator || direction && direction.designator || '',
        runwayDesignator: item.runwayDesignator || direction && direction.runwayDesignator || '',
        airport,
        threshold: threshold ? {
          id: threshold.id,
          role: threshold.role,
          position: { lat: Number(threshold.position.lat), lon: Number(threshold.position.lon) },
          validFrom: threshold.validFrom || '',
        } : null,
        validFrom: item.validFrom || '',
      };
      const list = systemsByDirection.get(system.runwayDirectionId) || [];
      list.push(system);
      systemsByDirection.set(system.runwayDirectionId, list);
      return system;
    });

    const runwayThresholds = [];
    context.runwayDirectionsById.forEach(direction => {
      const threshold = context.thresholdsByDirection.get(direction.id);
      if (!threshold || !direction.airport || !direction.airport.designator) return;
      runwayThresholds.push({
        directionId: direction.id,
        designator: direction.designator || threshold.designator || '',
        runwayDesignator: direction.runwayDesignator || '',
        airport: modules.core.airportSummary(direction.airport),
        threshold: {
          id: threshold.id,
          role: threshold.role,
          position: { lat: Number(threshold.position.lat), lon: Number(threshold.position.lon) },
          validFrom: threshold.validFrom || '',
        },
        papiSystems: (systemsByDirection.get(direction.id) || []).filter(item => item.type === 'PAPI'),
        validFrom: direction.validFrom || '',
      });
    });

    const thresholdsByAirport = new Map();
    runwayThresholds.forEach(item => {
      const icao = modules.core.normalized(item.airport.designator);
      const list = thresholdsByAirport.get(icao) || [];
      list.push(item);
      thresholdsByAirport.set(icao, list);
    });
    thresholdsByAirport.forEach(list => list.sort((a, b) => a.designator.localeCompare(b.designator, 'pt-BR', { numeric: true })));

    const runwayAirports = [...thresholdsByAirport.entries()].map(([designator, thresholds]) => ({
      designator,
      name: thresholds[0] && thresholds[0].airport.name || '',
      searchText: modules.core.normalized(`${designator} ${thresholds[0] && thresholds[0].airport.name || ''}`),
    })).sort((a, b) => a.designator.localeCompare(b.designator));

    const aids = visualAids.map(item => ({
      id: item.id,
      category: 'visual',
      type: item.type,
      designator: item.runwayDirectionDesignator ? `RWY ${item.runwayDirectionDesignator}` : '',
      name: item.airport && item.airport.name || item.type,
      position: item.threshold && item.threshold.position || null,
      positionKind: item.threshold ? 'threshold' : '',
      airport: item.airport,
      runway: item.runwayDirectionDesignator,
      runwayDesignator: item.runwayDesignator,
      side: item.side,
      slopeAngle: item.slopeAngle,
      minimumEyeHeightOverThreshold: item.minimumEyeHeightOverThreshold,
      numberOfBoxes: item.numberOfBoxes,
      validFrom: item.validFrom,
      searchText: modules.core.normalized([item.type, item.airport && item.airport.designator, item.airport && item.airport.name, item.runwayDirectionDesignator, item.side].filter(Boolean).join(' ')),
    }));

    return { visualAids, aids, runwayThresholds, thresholdsByAirport, runwayAirports };
  }

  modules.papi = { build };
})(window);
