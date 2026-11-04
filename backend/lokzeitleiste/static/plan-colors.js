/* Keep in sync with planning/palette.py. Calendar dates use UTC to avoid timezone shifts. */
(()=>{const colors={Arbeitstag:'#f5f5f5',Urlaub:'#ff7256',Ruhetag:'#66cdaa',Ungeplant:'#eef0f3',Feiertag:'#ffe4e1',Wochenende:'#eedc82'};
function weekend(day){return [0,6].includes(new Date(day.date+'T00:00:00Z').getUTCDay());}
function base(day){return colors[[globalThis.CtlText.source("backend_plan_colors.text_35d3a889824d"),globalThis.CtlText.source("backend_plan_colors.text_e79aa42d7d18")].includes(day.kind)?day.kind:weekend(day)?globalThis.CtlText.source("backend_plan_colors.text_fd7058ac0c38"):day.kind]||colors.Ungeplant;}
function apply(node,day){const color=base(day);node.dataset.planKind=day.kind;node.dataset.planHoliday=String(!!day.is_holiday);node.dataset.weekend=String(weekend(day));node.style.backgroundColor=day.is_holiday?colors.Feiertag:color;node.style.backgroundImage=day.is_holiday&&day.kind!==globalThis.CtlText.source("backend_plan_colors.text_52e37a639da5")?`linear-gradient(135deg,${colors.Feiertag} 0 50%,${color} 50% 100%)`:'none';}
function yearSlots(month){return Array.from({length:31},(_,i)=>month.days[i]||null);}
function weekdayInitial(date){return new Intl.DateTimeFormat(window.I18n?.locale||'de-DE',{weekday:'long',timeZone:'UTC'}).format(new Date(date+'T00:00:00Z')).slice(0,2);}
window.PlanColors={colors,weekend,base,apply,yearSlots,weekdayInitial};})();
