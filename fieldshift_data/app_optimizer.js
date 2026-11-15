// FieldShift rotation engine (browser version). Same rules as economics.py:
// profit = yield × rotation multiplier × price × scenario − cost − P removal (kg/ha ÷ 2.4710538) × P price
// Constraints: max consecutive same crop, minimum wheat seasons, fallow frequency (per region), winter-wheat sowing fit.
var FSOpt = (function () {
  var WHEAT = { "Winter Wheat": 1, "Spring Wheat": 1 };
  var FALLOW = "Fallow/Idle Cropland";

  function yearsWithoutFallow(seq) { var n = 0; for (var i = seq.length - 1; i >= 0; i--) { if (seq[i] === FALLOW) break; n++; } return n; }

  function yearProfit(D, region, crop, previous, opts) {
    var P = D.params;
    if (crop === FALLOW) {
      return P.fallow_cost === null ? { profit: null, missing: ["fallow cost"] } : { profit: -P.fallow_cost, missing: [] };
    }
    var e = (D.regions[region].inputs || {})[crop] || {};
    var missing = [];
    if (e.yield == null) missing.push(crop + " yield");
    if (e.price == null) missing.push(crop + " price");
    if (e.cost == null) missing.push(crop + " cost");
    if (P.p_price === null) missing.push("P fertilizer price");
    if (!D.p_removal[crop]) missing.push(crop + " P removal");
    if (missing.length) return { profit: null, missing: missing };
    var mult = 1;
    (P.rotation_effects || []).forEach(function (r) { if (r.previous === previous && r.crop === crop && (!r.region || r.region === region)) mult *= r.yield_multiplier; });
    var pCost = D.p_removal[crop].kg_p_per_ha / P.acres_per_ha * P.p_price;
    return { profit: e.yield * mult * e.price * (opts.price_factor || 1) - e.cost - pCost, missing: [] };
  }

  function evaluate(D, region, seq, previous, opts) {
    var total = 0, pTotal = 0, missing = [], yearly = [];
    for (var i = 0; i < seq.length; i++) {
      var crop = seq[i];
      var r = yearProfit(D, region, crop, i === 0 ? previous : seq[i - 1], opts);
      var removal = crop === FALLOW ? 0 : (D.p_removal[crop] ? D.p_removal[crop].kg_p_per_ha : null);
      yearly.push({ crop: crop, profit: r.profit, p_removal: removal, missing: r.missing });
      r.missing.forEach(function (m) { if (missing.indexOf(m) < 0) missing.push(m); });
      total = (r.profit === null || total === null) ? null : total + r.profit;
      pTotal = (removal === null || pTotal === null) ? null : pTotal + removal;
    }
    return { sequence: seq.slice(), total: total, p_total: pTotal, yearly: yearly, missing: missing };
  }

  function makeFeasible(D, site) {
    var memo = {};
    return function (previous, crop, index) {
      if (crop !== "Winter Wheat" || previous === null || previous === "Winter Wheat" || previous === FALLOW) return true;
      var key = previous + "|" + index;
      if (!(key in memo)) {
        var year = D.plan_years[0] + index;
        var rule = D.calendar[previous] || {};
        var w = D.windows[site] || {};
        var prev = (w[previous] || {})[year - 1];
        var wheat = (w["Winter Wheat"] || {})[year];
        if (rule.type !== "spring" || !rule.season_days || !prev || !prev.start || !wheat || !wheat.end) memo[key] = true;
        else {
          var harvest = new Date(prev.start + "T00:00:00Z"); harvest.setUTCDate(harvest.getUTCDate() + rule.season_days);
          memo[key] = harvest <= new Date(wheat.end + "T00:00:00Z");
        }
      }
      return memo[key];
    };
  }

  function valid(seq, opts, feasible, rule, initialRun) {
    var run = 1;
    for (var i = 1; i < seq.length; i++) {
      run = seq[i] === seq[i - 1] ? run + 1 : 1;
      if (run > opts.max_consecutive) return false;
    }
    var wheat = 0; seq.forEach(function (c) { if (WHEAT[c]) wheat++; });
    if (wheat < opts.min_wheat) return false;
    if (rule) {
      var streak = initialRun;
      for (var j = 0; j < seq.length; j++) { streak = seq[j] === FALLOW ? 0 : streak + 1; if (streak > rule.max_years_without_fallow) return false; }
    }
    for (var k = 1; k < seq.length; k++) if (!feasible(seq[k - 1], seq[k], k)) return false;
    return true;
  }

  function cmpSeq(a, b) { for (var i = 0; i < a.length; i++) { if (a[i] < b[i]) return -1; if (a[i] > b[i]) return 1; } return 0; }

  function optimize(D, region, crops, previous, initialRun, opts, site) {
    var years = D.plan_years.length, ranked = [], incomplete = {};
    if (!crops.length) return { ranked: [], incomplete: [] };
    if (Math.pow(crops.length, years) > 2000000) throw new Error("Too many combinations");
    var feasible = makeFeasible(D, site || region);
    var rule = opts.use_fallow_rule === false ? null : (D.regions[region].fallow_rule || null);
    var idx = []; for (var i = 0; i < years; i++) idx.push(0);
    while (true) {
      var seq = idx.map(function (j) { return crops[j]; });
      if (valid(seq, opts, feasible, rule, initialRun)) {
        var r = evaluate(D, region, seq, previous, opts);
        if (r.total === null) r.missing.forEach(function (m) { incomplete[m] = 1; });
        else ranked.push(r);
      }
      var p = years - 1;
      while (p >= 0 && idx[p] === crops.length - 1) { idx[p] = 0; p--; }
      if (p < 0) break;
      idx[p]++;
    }
    ranked.sort(function (a, b) { return (b.total - a.total) || cmpSeq(a.sequence, b.sequence); });
    return { ranked: ranked, incomplete: Object.keys(incomplete).sort() };
  }

  function strategies(D, parcel, opts) {
    var crops = opts.crops[parcel.region] || [];
    var res = optimize(D, parcel.region, crops, parcel.previous, parcel.initial_run, opts, parcel.site || parcel.region);
    var years = D.plan_years.length;
    var need = Math.max(opts.min_wheat, Math.round(D.params.wheat_share * years));
    var best = res.ranked[0] || null;
    var wheat = null;
    for (var i = 0; i < res.ranked.length; i++) {
      var r = res.ranked[i], n = 0; r.sequence.forEach(function (c) { if (WHEAT[c]) n++; });
      if (n >= need && (!best || cmpSeq(r.sequence, best.sequence) !== 0)) { wheat = r; break; }
    }
    return { best: best, wheat: wheat, wheat_need: need, current: evaluate(D, parcel.region, parcel.current, parcel.previous, opts),
             incomplete: res.incomplete, count: res.ranked.length };
  }

  return { optimize: optimize, strategies: strategies, evaluate: evaluate, yearsWithoutFallow: yearsWithoutFallow };
})();
if (typeof module !== "undefined") module.exports = FSOpt;
