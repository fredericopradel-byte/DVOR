(function (global) {
  'use strict';

  const modules = global.IVAixmModules = global.IVAixmModules || {};

  function equipmentDetails(navaid, equipmentById) {
    const linked = (navaid.equipmentIds || []).map(id => equipmentById.get(id)).filter(Boolean);
    const vor = linked.find(item => item.equipmentType === 'VOR');
    const dme = linked.find(item => item.equipmentType === 'DME');
    return {
      frequency: vor && vor.frequency || null,
      channel: dme && dme.channel || null,
      components: linked,
    };
  }

  function build(data) {
    const equipmentById = new Map((data.navaidEquipment || []).map(item => [item.id, item]));
    const navaids = (data.navaids || [])
      .filter(item => /(^|_)VOR($|_)/.test(item.type || '') && modules.core.finitePosition(item))
      .map(item => {
        const details = equipmentDetails(item, equipmentById);
        const airport = modules.core.airportSummary(item.airport);
        return {
          id: item.id,
          category: 'radio',
          type: item.type || 'VOR',
          designator: item.designator || '',
          name: item.name || '',
          position: { lat: Number(item.position.lat), lon: Number(item.position.lon) },
          positionKind: 'auxiliary',
          airport,
          frequency: details.frequency,
          channel: details.channel,
          elevation: item.elevation || (details.components.find(component => component.equipmentType === 'VOR') || {}).elevation || null,
          components: details.components,
          validFrom: item.validFrom || '',
          searchText: modules.core.normalized([item.designator, item.name, item.type, airport && airport.designator, airport && airport.name].filter(Boolean).join(' ')),
        };
      });
    return { navaids, aids: navaids };
  }

  modules.vor = { build };
})(window);
