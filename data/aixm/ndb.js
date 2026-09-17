(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};

  function build(data) {
    const equipmentById = new Map((data.navaidEquipment || []).map(item => [item.id, item]));
    const aids = (data.navaids || [])
      .filter(item => item.type === 'NDB' && modules.core.finitePosition(item))
      .map(item => {
        const equipment = (item.equipmentIds || []).map(id => equipmentById.get(id)).find(Boolean);
        const airport = modules.core.airportSummary(item.airport);
        return {
          id: item.id,
          category: 'radio',
          type: 'NDB',
          designator: item.designator || '',
          name: item.name || '',
          position: { lat: Number(item.position.lat), lon: Number(item.position.lon) },
          positionKind: 'auxiliary',
          airport,
          frequency: equipment && equipment.frequency || null,
          channel: null,
          elevation: item.elevation || equipment && equipment.elevation || null,
          components: equipment ? [equipment] : [],
          validFrom: item.validFrom || '',
          searchText: modules.core.normalized([item.designator, item.name, 'NDB', airport && airport.designator, airport && airport.name].filter(Boolean).join(' ')),
        };
      });
    return { aids };
  }

  modules.ndb = { build };
})(window);
