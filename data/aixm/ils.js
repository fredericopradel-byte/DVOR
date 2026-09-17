(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};

  function build(data, context) {
    const equipmentById = new Map((data.navaidEquipment || []).map(item => [item.id, item]));
    const systemTypes = new Set(['ILS', 'ILS_DME', 'LOC_DME']);
    const aids = (data.navaids || [])
      .filter(item => systemTypes.has(item.type) && modules.core.finitePosition(item))
      .map(item => {
        const components = (item.equipmentIds || []).map(id => equipmentById.get(id)).filter(Boolean);
        const localizer = components.find(component => component.equipmentType === 'Localizer');
        const glidepath = components.find(component => component.equipmentType === 'Glidepath');
        const dme = components.find(component => component.equipmentType === 'DME');
        const markers = components.filter(component => component.equipmentType === 'MarkerBeacon');
        const direction = context.runwayDirectionsById.get(item.runwayDirectionId) || null;
        const airport = modules.core.airportSummary(item.airport || direction && direction.airport);
        return {
          id: item.id,
          category: 'landing',
          type: item.type,
          designator: item.designator || '',
          name: item.name || '',
          position: { lat: Number(item.position.lat), lon: Number(item.position.lon) },
          positionKind: 'localizer',
          airport,
          runway: direction && direction.designator || '',
          runwayDesignator: direction && direction.runwayDesignator || '',
          frequency: localizer && localizer.frequency || null,
          glidepathFrequency: glidepath && glidepath.frequency || null,
          channel: dme && dme.channel || null,
          elevation: item.elevation || localizer && localizer.elevation || null,
          components,
          markers,
          validFrom: item.validFrom || '',
          searchText: modules.core.normalized([item.designator, item.name, item.type, airport && airport.designator, airport && airport.name, direction && direction.designator].filter(Boolean).join(' ')),
        };
      });
    return { aids };
  }

  modules.ils = { build };
})(window);
