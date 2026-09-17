(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};

  function build(data) {
    const equipmentById = new Map((data.navaidEquipment || []).map(item => [item.id, item]));
    const dmeIds = new Set((data.navaidEquipment || []).filter(item => item.equipmentType === 'DME').map(item => item.id));
    const compositeDmeIds = new Set();
    (data.navaids || []).forEach(item => {
      if (!['VOR_DME', 'ILS_DME', 'LOC_DME'].includes(item.type)) return;
      (item.equipmentIds || []).forEach(id => { if (dmeIds.has(id)) compositeDmeIds.add(id); });
    });

    const aids = (data.navaids || [])
      .filter(item => item.type === 'DME' && modules.core.finitePosition(item))
      .filter(item => !(item.equipmentIds || []).some(id => compositeDmeIds.has(id)))
      .map(item => {
        const equipment = (item.equipmentIds || []).map(id => equipmentById.get(id)).find(Boolean);
        const airport = modules.core.airportSummary(item.airport);
        return {
          id: item.id,
          category: 'radio',
          type: 'DME',
          designator: item.designator || '',
          name: item.name || '',
          position: { lat: Number(item.position.lat), lon: Number(item.position.lon) },
          positionKind: 'auxiliary',
          airport,
          frequency: null,
          channel: equipment && equipment.channel || null,
          elevation: item.elevation || equipment && equipment.elevation || null,
          components: equipment ? [equipment] : [],
          validFrom: item.validFrom || '',
          searchText: modules.core.normalized([item.designator, item.name, 'DME', airport && airport.designator, airport && airport.name].filter(Boolean).join(' ')),
        };
      });
    return { aids };
  }

  modules.dme = { build };
})(window);
