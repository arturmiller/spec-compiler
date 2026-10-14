/** Project-local German catalog. Missing keys and placeholders fail the build. */
export const DE_MESSAGES = {};
function put(prefix, values) {
  for (const [key, value] of Object.entries(values)) DE_MESSAGES[prefix + '.' + key] = value;
}
put('page', {title: '{title} – Diagramm'});
put('diagram.description', {
  architecture: 'Eine mit Archify erzeugte Architekturansicht.',
  workflow: 'Ein mit Archify erzeugter Ablauf.',
  sequence: 'Eine mit Archify erzeugte Sequenzansicht.',
  dataflow: 'Ein mit Archify erzeugter Datenfluss.',
  lifecycle: 'Ein mit Archify erzeugter Lifecycle.'
});
put('node', {focus: '{label} auswählen', 'focus.detail': '{label} auswählen, {detail}',
  'context.architecture': 'Architekturbaustein', 'context.workflow': 'Ablaufschritt',
  'context.sequence': 'Teilnehmer', 'context.dataflow': 'Datenflussknoten', 'context.lifecycle': 'Zustand'});
put('legend', {title: 'Legende'});
put('legend.architecture', {frontend: 'Frontend', backend: 'Backend', database: 'Datenspeicher', cloud: 'Cloud-Dienst',
  security: 'Sicherheit', messagebus: 'Nachrichten', external: 'Externes System'});
put('legend.workflow', {frontend: 'Benutzeroberfläche', backend: 'Agentenlogik', security: 'Richtlinie',
  messagebus: 'Werkzeugaufruf', database: 'Kontext / Ablaufspur', cloud: 'Cloud-Dienst', external: 'Externes System'});
put('legend.sequence', {emphasis: 'Anfrage', return: 'Antwort', security: 'Sicherheit', dashed: 'Asynchrone Spur', default: 'Nachricht'});
put('legend.dataflow', {emphasis: 'Primärdaten', security: 'Richtlinie / personenbezogene Daten', dashed: 'Asynchrone Verarbeitung',
  database: 'Datenspeicher', default: 'Datenfluss'});
put('legend.lifecycle', {start: 'Start', active: 'Aktiver Zustand', waiting: 'Warten', decision: 'Entscheidung',
  success: 'Erfolgreicher Endzustand', failure: 'Fehler / Ende', neutral: 'Neutral', external: 'Extern'});
put('viewer.kind', {frontend: 'Frontend', backend: 'Backend', database: 'Datenspeicher', cloud: 'Cloud-Dienst',
  security: 'Sicherheit', messagebus: 'Nachrichten', external: 'Extern', neutral: 'Neutral', node: 'Knoten',
  start: 'Start', active: 'Aktiv', waiting: 'Warten', decision: 'Entscheidung', success: 'Erfolg', failure: 'Fehler'});
put('viewer.toolbar', {actions: 'Diagrammaktionen'});
put('viewer.theme', {'toggle.title': 'Farbschema wechseln (T)', toggle: 'Farbschema wechseln', dark: 'Dunkel', light: 'Hell'});
put('viewer.preset', {
  'choose.title': 'Darstellung wählen (S wechselt)', choose: 'Darstellung wählen', style: 'Darstellung',
  menu: 'Darstellung', identity: 'Visuelle Darstellung', cycles: 'S wechselt', classic: 'Klassisch',
  'classic.short': 'Klassisch', 'classic.hint': 'Stabile technische Standardansicht', flow: 'Signalfluss',
  'flow.short': 'Fluss', 'flow.hint': 'Darstellung mit Bewegung', blueprint: 'Technikplan',
  'blueprint.hint': 'Technische Prüfung', editorial: 'Publikation', 'editorial.hint': 'Veröffentlichung und Einführung',
  'badge.signalFlow': 'SIGNALFLUSS', 'badge.blueprint': 'TECHNIKPLAN / REV 01',
  'badge.editorial': 'PUBLIKATION / NOTIZ', 'badge.editorialPlate': 'ARCHIFY / ABBILDUNG 04',
  current: 'Darstellung: {style}. Darstellung wählen'
});
put('viewer.motion', {
  live: 'Bewegt', still: 'Statisch', pause: 'Bewegung pausieren', resume: 'Bewegung fortsetzen',
  reduced: 'Bewegung aufgrund der Einstellung für reduzierte Bewegung pausiert',
  hidden: 'Bewegung pausiert, solange diese Seite verborgen ist',
  yielding: 'Bewegung pausieren; aktuell hat {owner} Vorrang',
  'yielding.title': 'Bewegte Vorschau aktiv · {owner} hat Vorrang'
});
put('viewer.owner', {story: 'die geführte Geschichte', chapter: 'das aktive Kapitel',
  chapterPreview: 'die Kapitelvorschau', handoff: 'der Kapitelübergang', route: 'die Pfadsuche',
  lens: 'der Typenvergleich', relationship: 'die Beziehungsvorschau', intent: 'die Vorschau',
  focus: 'die Auswahl', legend: 'die Legendenvorschau', reader: 'die Leserinteraktion'});
put('viewer.present', {
  enter: 'Präsentationsmodus öffnen', 'enter.title': 'Präsentationsmodus (F)',
  exit: 'Präsentationsmodus verlassen', 'exit.title': 'Präsentationsmodus verlassen (F oder Escape)',
  present: 'Präsentieren', 'exit.label': 'Zurück'
});
put('viewer.export', {
  button: 'Exportieren', 'button.title': 'Diagramm exportieren (E)', diagram: 'Diagramm exportieren',
  menu: 'Exportieren', subtitle: 'Portable, bereinigte Ausgaben', share: 'Teilen',
  shareCard: 'Vorschaukarte', routeShareCard: 'Pfadkarte', reachShareCard: 'Erreichbarkeitskarte',
  copyShareCard: 'Vorschaukarte kopieren', copyDiagram: 'Diagramm kopieren', clipboardPng: 'PNG in die Zwischenablage',
  raster: 'Rasterbilder', image: 'Bild', lossless: 'Verlustfreies Bild', compact: 'Kompaktes Bild',
  modern: 'Modernes Bildformat', vectorMotion: 'Vektor und Bewegung', 'vectorMotion.heading': 'Vektor und Bewegung',
  editable: 'Bearbeitbarer Vektor', motion6s: '6 s Bewegung', unsupported: 'Von diesem Browser nicht unterstützt',
  clipboardUnsupported: 'Bildkopie in die Zwischenablage wird nicht unterstützt',
  'clipboardUnsupported.period': 'Bildkopie in die Zwischenablage wird nicht unterstützt.',
  'clipboardUnsupported.short': 'Dieser Browser unterstützt keine Bildkopie.',
  motionUnavailable: 'Bewegungsaufzeichnung ist in diesem Browser nicht verfügbar',
  webmUnavailable: 'WebM ist in diesem Browser nicht verfügbar', failed: 'Export fehlgeschlagen: {message}',
  unknownVariant: 'Unbekannte Kartenvariante: {variant}', routeRequired: 'Vor dem Export einer Pfadkarte einen Pfad auswählen',
  reachRequired: 'Vor dem Export einer Erreichbarkeitskarte deklarierte Erreichbarkeit auswählen',
  unknown: 'Unbekannt', routeFailed: 'Pfadkartenexport fehlgeschlagen: {message}',
  reachFailed: 'Erreichbarkeitskartenexport fehlgeschlagen: {message}', copyFailed: 'Kopieren fehlgeschlagen: {message}',
  copiedPng: 'PNG in die Zwischenablage kopiert', copiedShare: 'Vorschaukarte kopiert',
  downloadedShare: 'Vorschaukarte heruntergeladen', downloadedRoute: 'Pfadkarte heruntergeladen',
  downloadedReach: 'Erreichbarkeitskarte heruntergeladen', downloadedWebm: 'WebM heruntergeladen',
  recording: '6 Sekunden Bewegung werden aufgezeichnet …',
  'card.routeSummary.one': 'Pfad: {source} → {target} · {count} gerichteter Schritt',
  'card.routeSummary.other': 'Pfad: {source} → {target} · {count} gerichtete Schritte',
  'card.reachSummary': 'Deklarierte {direction} ab {origin} · {nodes} · {links} · maximal {hops}',
  'card.node.one': '{count} Knoten', 'card.node.other': '{count} Knoten',
  'card.link.one': '{count} Verbindung', 'card.link.other': '{count} Verbindungen',
  'card.hop.one': '{count} Schritt', 'card.hop.other': '{count} Schritte',
  'card.routeBadge': 'ARCHIFY · PFAD · {hops}', 'card.reachBadge': 'ARCHIFY · {direction} ERREICHBARKEIT',
  'card.defaultBadge': 'ARCHIFY · {preset} · {theme}', 'direction.upstream': 'Vorgänger', 'direction.downstream': 'Nachfolger',
  'error.canvasUnavailable': 'Canvas für {label} nicht verfügbar',
  'error.contextUnavailable': '2D-Canvas-Kontext für {label} nicht verfügbar',
  'error.toBlobUnavailable': 'canvas.toBlob für {label} nicht verfügbar',
  'error.toBlobNull': 'canvas.toBlob hat für {label} keine Daten zurückgegeben',
  'error.variantsCombined': 'Kartenvarianten können nicht kombiniert werden',
  'error.viewerState': 'Temporärer Viewer-Zustand konnte beim Kartenexport nicht entfernt werden',
  'error.routeState': 'Der ausgewählte Pfad konnte beim Export nicht sicher erhalten werden',
  'error.reachState': 'Deklarierte Erreichbarkeit konnte beim Export nicht sicher erhalten werden',
  'error.webmRequirements': 'WebM benötigt eine Ablaufanimation und MediaRecorder-Unterstützung im Browser',
  'error.mediaRecorder': 'MediaRecorder fehlgeschlagen', 'error.emptyWebm': 'MediaRecorder erzeugte eine leere WebM-Datei',
  'error.webmBackground': 'SVG-Hintergrund konnte für den WebM-Export nicht geladen werden'
});
put('viewer.guided', {
  region: 'Geführte Diagrammansichten', previous: 'Vorherige Ansicht', 'previous.title': 'Vorherige Ansicht ([)',
  next: 'Nächste Ansicht', 'next.title': 'Nächste Ansicht (])', views: 'Geführte Ansichten',
  explore: 'Dieses System erkunden', intro: 'Deklarierte Pfade durchlaufen, ohne das Quelldiagramm zu verändern.',
  trail: 'Ablaufspur', beat: 'Schritt', nextBeat: 'Weiter', play: 'Geführten Ablauf starten',
  'play.title': 'Geführten Ablauf starten (P)', pause: 'Geführten Ablauf pausieren',
  'pause.title': 'Geführten Ablauf pausieren (P)', replay: 'Geführten Ablauf erneut starten',
  'replay.title': 'Geführten Ablauf erneut starten (P)', playStory: 'Ablauf starten', pauseStory: 'Pausieren',
  replayStory: 'Erneut starten', motionUnavailable: 'Im statischen Modus ist die Ablaufwiedergabe nicht verfügbar',
  enableMotion: 'Für die Ablaufwiedergabe Bewegung aktivieren',
  selectBeatLink: 'Einen Ablaufschritt auswählen, um seinen genauen Link zu kopieren',
  copyMoment: 'Schritt kopieren', momentCopied: 'Link zum Schritt kopiert',
  momentCopyFailed: 'Link zum Ablaufschritt konnte nicht kopiert werden', copied: 'Kopiert',
  copyFailed: 'Kopieren fehlgeschlagen', showAll: 'Alles zeigen', 'showAll.aria': 'Gesamtes Diagramm zeigen',
  chapters: 'Kapitel', storyTrail: 'Ablaufspur für {label}: {count} Schritte',
  'chapter.open': 'Kapitel {index} von {total} öffnen: {label}, {count} Stationen',
  'chapter.current': 'Aktuelles Kapitel {index} von {total}: {label}, {count} Stationen',
  'chapter.selectedNodes': '{count} ausgewählte Knoten', 'chapter.stops': '{count} Stationen',
  'chapter.stop.one': '{count} Station', 'chapter.stop.other': '{count} Stationen',
  'chapter.current.title': '{label} – aktuelles Kapitel, {count} Stationen',
  'chapter.delta.expanded': '{stay} bleiben, {enter} kommen hinzu, {leave} entfallen',
  'chapter.delta.aria': 'Kapitel {index} von {total} öffnen: {label}. Änderung der Auswahl: {delta}',
  'chapter.delta.title': '{label} – {delta} Kapitelauswahl', handoff: '{from} → {to} · über {label}',
  'share.chapter': 'Kapitel {index} / {total}', 'share.initial': 'Kapitel 01 / 01',
  'share.default': 'Geführtes Kapitel', 'state.ready': 'Bereit', 'state.playing': 'Wiedergabe',
  'state.settled': 'Abgeschlossen', 'state.paused': 'Pausiert', 'state.pinned': 'Fixiert', 'state.still': 'Statisch',
  'share.step': 'Schritt {index} / {total} · {label}', 'share.staticMoment': '{step} · Statischer Schritt',
  'share.complete': '{count} Schritte abgeschlossen · {note}', 'share.settled': 'Der Pfad ist zum Lesen bereit.',
  'share.staticPath': '{count} Schritte · Statischer Pfad', 'share.ready': '{count} Schritte · Bereit',
  'share.aria': '{state} Kapitel {index} von {total}: {label}. {beat}. {route}',
  'beat.start': 'Schritt {index} / {total} · {label} · Ausgangspunkt',
  'beat.forward': 'Schritt {index} / {total} · {from} → {to}',
  'beat.reverse': 'Schritt {index} / {total} · {from} → {to} · Deklarierte Beziehung in Gegenrichtung',
  'beat.multiple': 'Schritt {index} / {total} · {from} ⇄ {to} · {count} deklarierte Beziehungen',
  'beat.group': 'Schritt {index} / {total} · {from} · {to} · Gruppiert · Keine direkte Beziehung',
  'beat.aria.prefix': 'Ablaufschritt {index} von {total}: {label}. ',
  'beat.aria.start': 'Ausgangspunkt.',
  'beat.aria.forward': 'Von {from} über eine deklarierte Beziehung in Vorwärtsrichtung.',
  'beat.aria.reverse': 'Von {from}; die deklarierte Beziehung zeigt von {to} nach {from}.',
  'beat.aria.multiple': 'Von {from} über {count} deklarierte Beziehungen; ohne willkürliche Bewegung dargestellt.',
  'beat.aria.group': 'Mit {from} gruppiert, ohne direkt deklarierte Beziehung.',
  'caption.start': 'Ausgangspunkt', 'caption.grouped': 'Gruppierter Übergang · Keine direkte Beziehung',
  'caption.more': ' +{count} weitere', 'caption.reverse': 'Deklarierte Beziehung in Gegenrichtung',
  'caption.relationships': '{count} deklarierte Beziehungen', 'caption.relationship': 'Deklarierte Beziehung',
  'caption.direction': 'Deklarierte Richtung: {from} → {to}', 'caption.starting': 'Deklarierter Ausgangspunkt',
  beatLink: 'Link zum aktuellen Ablaufschritt kopieren: Schritt {index} von {total}: {label}',
  noStory: 'Dieses Diagramm hat keinen deklarierten geführten Ablauf.'
});
put('viewer.guide', {
  eyebrow: 'Diagrammhilfe', close: 'Diagrammhilfe schließen', inspecting: 'Kompilierte Semantik untersuchen',
  actions: 'Aktionen zur Diagrammerkundung', find: 'Knoten finden',
  'find.hint': 'Beschriftungen, Verantwortungen, Typen und stabile IDs durchsuchen.',
  route: 'Pfad verfolgen', 'route.aria': 'Gerichteten Pfad verfolgen',
  'route.hint': 'Deklarierte Verbindungen zwischen zwei Knoten in ihrer Richtung prüfen.',
  map: 'Gesamtes System ansehen', 'map.hint': 'Übersicht mit aktuellem Ausschnitt und stabilen Knoten öffnen.',
  lens: 'Typen vergleichen', 'lens.hint': 'Rollen zählen und direkt deklarierte Beziehungen vergleichen.',
  story: 'Geführten Ablauf starten', 'story.hint': 'Deklarierte Kapitel und tatsächliche Beziehungen durchlaufen.',
  present: 'Präsentationsmodus öffnen', 'present.hint': 'Den Ausschnitt dem Diagramm geben, ohne den Export zu verändern.',
  shortcuts: 'Weitere Tastenkürzel', 'shortcut.export': 'Exportieren', 'shortcut.theme': 'Farbschema',
  'shortcut.style': 'Darstellung', 'shortcut.reset': 'Zurücksetzen', 'shortcut.zoomIn': 'Vergrößern',
  'shortcut.zoomOut': 'Verkleinern', 'shortcut.close': 'Schließen',
  facts: '{nodes} · {relationships} · {views}', 'fact.node.one': '{count} semantischer Knoten',
  'fact.node.other': '{count} semantische Knoten', 'fact.relationship.one': '{count} Beziehung',
  'fact.relationship.other': '{count} Beziehungen', 'fact.view.one': '{count} geführte Ansicht',
  'fact.view.other': '{count} geführte Ansichten', 'story.available.one': '{count} deklariertes Kapitel und seine Beziehungen durchlaufen.',
  'story.available.other': '{count} deklarierte Kapitel und ihre Beziehungen durchlaufen.',
  'story.unavailable': 'Kein deklarierter geführter Ablauf in diesem Diagramm.',
  open: 'Diagrammhilfe öffnen', noStory: 'Dieses Diagramm hat keinen deklarierten geführten Ablauf.'
});
put('viewer.finder', {
  title: 'Knoten finden', close: 'Knotensuche schließen', placeholder: 'Beschriftungen oder IDs durchsuchen',
  search: 'Diagrammknoten durchsuchen', results: 'Diagrammknoten', empty: 'Keine passenden Knoten',
  'result.focus': '{label} auswählen', 'result.routeStart': '{label} als Pfadbeginn wählen',
  'result.routeTarget': '{label} als Pfadziel wählen, {links}', 'status.empty': 'Keine passenden Knoten',
  'status.count.one': '{count} passender Knoten', 'status.count.other': '{count} passende Knoten',
  'noun.nodes': 'Knoten', 'link.one': '{count} Verbindung', 'link.other': '{count} Verbindungen',
  'result.focus.one': '{label} auswählen, {count} zugehörige Verbindung',
  'result.focus.other': '{label} auswählen, {count} zugehörige Verbindungen',
  'status.filtered': '{visible} von {available} {noun}', 'status.all': '{available} {noun}'
});
put('viewer.passport', {
  eyebrow: 'Knotendetails', metadata: 'Knotenmetadaten', evidence: 'Geprüfte Quellennachweise',
  verified: 'Geprüfte Quelle', verificationScope: 'Im lokalen Git gegen die festgelegte Revision geprüft. Der Remote-Zugriff wurde nicht geprüft.',
  reach: 'Deklarierte Erreichbarkeit', 'reach.trace': 'Deklarierte Erreichbarkeit verfolgen',
  upstream: 'Vorgänger', downstream: 'Nachfolger', 'upstream.trace': 'Deklarierte Vorgänger verfolgen',
  'downstream.trace': 'Deklarierte Nachfolger verfolgen', close: 'Knotendetails schließen',
  copy: 'Link kopieren', 'copy.focus': 'Link zum ausgewählten Knoten kopieren', relations: 'Beziehungen',
  'relations.show': 'Verbundene Beziehungen zeigen', 'relations.hide': 'Verbundene Beziehungen verbergen',
  'relations.list': 'Verbundene Beziehungen', copyRelation: 'Beziehung kopieren', copyNode: 'Knoten kopieren',
  copyPinned: 'Link zur fixierten Beziehung kopieren', copySource: 'Link zum Quellknoten kopieren',
  'copy.focused.success': 'Knotenlink kopiert', 'copy.pinned.success': 'Beziehungslink kopiert',
  'copy.focused.failed': 'Knotenlink konnte nicht kopiert werden', 'copy.pinned.failed': 'Beziehungslink konnte nicht kopiert werden',
  'relationship.none': 'Keine verbundenen Beziehungen', 'relationship.count.one': '{count} Beziehung',
  'relationship.count.other': '{count} Beziehungen', 'relationship.show.one': '{count} verbundene Beziehung zeigen',
  'relationship.show.other': '{count} verbundene Beziehungen zeigen',
  'relationship.summary': '{out} ausgehend · {in} eingehend{loops}', 'relationship.loops': ' · {count} Schleife',
  'relationship.explorer': 'Direkte Beziehungen erkunden',
  'relationship.help': 'Mit Pfeiltasten Beziehungen erkunden. Enter oder Leertaste fixiert Details; Escape hebt die Auswahl auf.',
  'relationship.loopsBack': 'führt zurück', 'relationship.connectsTo': 'verbindet mit',
  'relationship.connectsFrom': 'verbindet von',
  'relationship.pinned': 'Fixierte Beziehung · {from} → {to} · {label}',
  'relationship.inspect': 'Beziehung {index} von {total} untersuchen: {from} nach {to}, {label}. Enter zeigt Details.',
  'relationship.group.out': 'Ausgehend', 'relationship.group.in': 'Eingehend', 'relationship.group.loop': 'Selbstbeziehungen',
  'relationship.row': '{group}: {relationship}, {neighbor}', 'relationship.direction.out': 'AUS →',
  'relationship.direction.in': '← EIN', 'relationship.direction.loop': 'SCHLEIFE',
  'sourceCount.one': '{count} geprüfter Quellenverweis', 'sourceCount.other': '{count} geprüfte Quellenverweise',
  sourceMarker: 'QUELLE', 'beacon.one': '{count} geprüfte Quelle; Knoten auswählen, um sie zu prüfen',
  'beacon.other': '{count} geprüfte Quellen; Knoten auswählen, um sie zu prüfen',
  'repository.open': 'Geprüfte Repository-Revision {revision} öffnen',
  'source.open': 'Geprüfte Quelle {path} bei Revision {revision} öffnen', 'source.openLink': 'Öffnen ↗',
  'reach.upstream.one': '{count} deklarierten Vorgänger verfolgen',
  'reach.upstream.other': '{count} deklarierte Vorgänger verfolgen',
  'reach.downstream.one': '{count} deklarierten Nachfolger verfolgen',
  'reach.downstream.other': '{count} deklarierte Nachfolger verfolgen',
  'reach.noUpstream': 'Keine deklarierten Vorgänger', 'reach.noDownstream': 'Keine deklarierten Nachfolger',
  'reach.status': '{direction} · {nodes} Knoten · {links} Verbindungen · maximal {hops} Schritte'
});
put('viewer.route', {
  eyebrow: 'Pfadsuche', start: 'Startknoten wählen', 'start.find': 'Start finden',
  'start.find.aria': 'Pfadbeginn finden', copy: 'Link kopieren', 'copy.aria': 'Link zum ausgewählten Pfad kopieren',
  clear: 'Zurücksetzen', 'clear.aria': 'Pfadsuche zurücksetzen', traced: 'Ausgewählter Pfad',
  pickTwo: 'Zwei Knoten im Diagramm wählen', pickOne: 'Einen Knoten im Diagramm wählen',
  controls: 'Pfadwiedergabe', previous: 'Vorherige Pfadposition', play: 'Pfadwiedergabe starten',
  pause: 'Pfadwiedergabe pausieren', replay: 'Pfadwiedergabe erneut starten', next: 'Nächste Pfadposition',
  journey: 'Wiedergabe', 'pause.label': 'Pausieren', 'replay.label': 'Erneut starten',
  overview: 'Übersicht', 'overview.aria': 'Vollständigen Pfad zeigen',
  instructions: 'Zuerst die Quelle, dann das Ziel wählen. Die Richtung ist relevant.',
  destination: 'Ziel ab {label} wählen', 'destination.find': 'Ziel finden',
  'destination.find.aria': 'Erreichbares Pfadziel finden', differentDestination: 'Anderes Ziel wählen',
  distinct: 'Ein Pfad benötigt zwei unterschiedliche Knoten.', unreachable: 'Kein gerichteter Pfad nach {label}',
  'unreachable.detail': '{target} ist von {source} aus nicht erreichbar. Ein hervorgehobenes Ziel wählen.',
  'start.instructions': 'Die Quelle wählen. Danach werden ausschließlich gerichtete Ziele angezeigt.',
  'copy.success': 'Pfadlink kopiert', 'copy.failed': 'Pfadlink konnte nicht kopiert werden',
  position: 'Pfadposition {index} von {total}: {label}', step: 'Schritt {index} von {total} · {phase} · {label}',
  motionRequired: 'Automatische Wiedergabe benötigt Bewegung', 'trigger.clear': 'Ausgewählten Pfad zurücksetzen',
  'overview.status': '{nodes} · {hops} · Kürzester deklarierter Pfad',
  'overview.node.one': '{count} Knoten', 'overview.node.other': '{count} Knoten',
  'overview.hop.one': '{count} gerichteter Schritt', 'overview.hop.other': '{count} gerichtete Schritte',
  'phase.playing': 'Wiedergabe', 'phase.complete': 'Abgeschlossen', 'phase.inspecting': 'Untersuchen',
  'destination.count.one': '{count} gerichtetes Ziel verfügbar. Einen hervorgehobenen Knoten wählen.',
  'destination.count.other': '{count} gerichtete Ziele verfügbar. Einen hervorgehobenen Knoten wählen.',
  noOutgoing: 'Hier beginnt kein ausgehender Pfad. Zurücksetzen und eine andere Quelle wählen.',
  'result.title': '{source} nach {target}', 'finder.source.title': 'Pfadbeginn wählen',
  'finder.source.placeholder': 'Pfadquellen durchsuchen', 'finder.source.empty': 'Keine passenden Pfadquellen',
  'finder.source.results': 'Knoten mit ausgehendem Pfad', 'finder.source.noun': 'Pfadquellen',
  'finder.source.badge': 'Start', 'finder.target.title': 'Ziel ab {label}',
  'finder.target.placeholder': 'Erreichbare Ziele durchsuchen', 'finder.target.empty': 'Keine passenden erreichbaren Ziele',
  'finder.target.results': 'Erreichbare Pfadziele', 'finder.target.noun': 'Erreichbare Ziele',
  'hop.one': '{count} Schritt', 'hop.other': '{count} Schritte'
});
put('viewer.lens', {
  eyebrow: 'Typenvergleich', title: 'Systemrollen vergleichen', close: 'Typenvergleich schließen',
  instruction: 'Bis zu zwei Typen wählen. Einer zeigt seine Beziehungen; zwei vergleichen ausschließlich direkt deklarierte Beziehungen.',
  kinds: 'Semantische Typen', choose: 'Einen Typ wählen, um seine Knoten und verbundenen Beziehungen zu prüfen.',
  copy: 'Link zum Typenvergleich kopieren', clear: 'Typenvergleich zurücksetzen', open: 'Typenvergleich öffnen',
  openActive: 'Aktiven Typenvergleich öffnen', legend: 'Semantische Legende',
  'legend.inspect.one': '{label} untersuchen, {count} Knoten', 'legend.inspect.other': '{label} untersuchen, {count} Knoten',
  'kind.count.one': '{label}, {count} Knoten', 'kind.count.other': '{label}, {count} Knoten',
  'compare.one': '{first} → {second}: {forward} · {second} → {first}: {reverse} · {count} direkte Beziehung',
  'compare.other': '{first} → {second}: {forward} · {second} → {first}: {reverse} · {count} direkte Beziehungen',
  single: '{nodes} · {relationships} · Verbundene Nachbarn bleiben sichtbar',
  'node.one': '{count} {label}-Knoten', 'node.other': '{count} {label}-Knoten',
  'relationship.one': '{count} verbundene Beziehung', 'relationship.other': '{count} verbundene Beziehungen'
});
put('viewer.radar', {
  title: 'Diagrammübersicht', building: 'Übersicht wird aufgebaut', openFull: 'Vollständige Übersicht öffnen',
  open: 'Übersicht öffnen', close: 'Übersicht schließen',
  surface: 'Diagrammübersicht. Knoten anklicken, um ihn auszuwählen, oder mit Pfeiltasten die Ansicht verschieben.',
  click: 'Knoten anklicken', drag: 'Zum Verschieben ziehen', space: 'Die Übersicht benötigt mehr Platz.',
  nodes: 'Knoten der Diagrammübersicht', focus: '{label} aus der Übersicht auswählen',
  status: '{count} Knoten · {viewport}', fullMap: '{count} Knoten · Vollständige Übersicht',
  compacted: 'Übersicht verkleinert, damit Knotendetails und Ansichtssteuerung sichtbar bleiben.',
  cancelWaiting: 'Wartende Übersicht schließen', needsSpace: 'Die Übersicht benötigt mehr sichtbaren Platz',
  'viewport.full': 'Vollständige Übersicht', 'viewport.width': '{percent}% Breite', 'viewport.scale': '{percent}% Ausschnitt'
});
put('viewer.nav', {
  controls: 'Ansichtssteuerung', route: 'Gerichteten Pfad verfolgen', 'route.title': 'Pfad verfolgen (R)',
  'route.short': 'PFAD', radar: 'Diagrammübersicht öffnen', 'radar.title': 'Diagrammübersicht (M)',
  'radar.short': 'KARTE', lens: 'Typenvergleich öffnen', 'lens.title': 'Typenvergleich (L)', 'lens.short': 'TYPEN',
  find: 'Knoten finden', 'find.title': 'Knoten finden (/)', guide: 'Diagrammhilfe öffnen', 'guide.title': 'Diagrammhilfe (?)',
  zoomOut: 'Verkleinern', 'zoomOut.title': 'Verkleinern (-)', reset: 'Diagrammansicht zurücksetzen',
  'reset.title': 'Ansicht zurücksetzen (0)', read: 'LESEN', zoomIn: 'Vergrößern', 'zoomIn.title': 'Vergrößern (+)',
  camera: '{hint}. Diagrammansicht zurücksetzen', 'camera.title': '{semantic}{hint} · Ansicht zurücksetzen (0)',
  'camera.semantic': 'Automatische Auswahlansicht aktiv · ', 'level.map': 'KARTE', 'level.read': 'LESEN',
  'level.full': 'DETAILS', 'level.auto': 'AUTO', 'detail.map': 'Vergrößern, um Beziehungen und Knotenbeschreibungen zu sehen',
  'detail.read': 'Weiter vergrößern, um Markierungen und Anmerkungen zu sehen', 'detail.full': 'Vollständige Diagrammdetails'
});
put('viewer.intent', {
  summary: '{label}. {out} ausgehend, {in} eingehend{loops}. {total} Verbindungen. Enter zeigt Details.',
  loops: ', {count} Selbstbeziehung'
});
put('viewer.common', {copied: 'Kopiert', copyFailed: 'Kopieren fehlgeschlagen', copyLink: 'Link kopieren',
  clear: 'Zurücksetzen', close: 'Schließen'});
