export type PartyMatch = {
  /** Standard label to show in UI, e.g. "BJP Votes" */
  label: string;
  /** 0..1 confidence */
  confidence: number;
};

type PartyDefinition = {
  label: string;
  variants: string[];
  /** Optional short codes to match as substrings (e.g. BJP, AIADMK) */
  abbreviations?: string[];
};

function normalizeForMatch(input: string): string {
  return input
    .toUpperCase()
    .replace(/[\u200E\u200F\u202A-\u202E]/g, "") // strip bidi controls
    .replace(/[^A-Z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function normalizeNoSpace(input: string): string {
  return normalizeForMatch(input).replace(/\s+/g, "");
}

function reverseChars(input: string): string {
  return input.split("").reverse().join("");
}

function reverseWords(input: string): string {
  const words = input.split(/\s+/).filter(Boolean);
  return words.reverse().join(" ");
}

function reverseEachWord(input: string): string {
  const words = input.split(/\s+/).filter(Boolean);
  return words.map(reverseChars).join(" ");
}

function extractTailAfterDash(original: string): string {
  // Common Excel header: "CANDIDATE - PARTY"
  if (original.includes(" - ")) {
    const parts = original.split(" - ");
    return parts[parts.length - 1].trim();
  }
  if (original.includes("-")) {
    const parts = original.split("-");
    return parts[parts.length - 1].trim();
  }
  return original.trim();
}

function tokenSet(s: string): Set<string> {
  const tokens = normalizeForMatch(s).split(" ").filter(Boolean);
  return new Set(tokens);
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let inter = 0;
  for (const t of a) if (b.has(t)) inter++;
  const union = a.size + b.size - inter;
  return union === 0 ? 0 : inter / union;
}

// ──────────────────────────────────────────────
// Party definitions — only canonical name variants needed.
// Reversed forms are auto-generated in PARTY_INDEX.
// ──────────────────────────────────────────────
// IMPORTANT: Order matters for disambiguation.
// More specific parties (e.g. CPI(M)) must come BEFORE less specific (CPI).
// Parties with abbreviations that are substrings of others need careful ordering.

const PARTIES: PartyDefinition[] = [
  // ── Major parties ──
  {
    label: "DMK Votes",
    abbreviations: ["DMK"],
    variants: [
      "DRAVIDA MUNNETRA KAZHAGAM",
      "D.M.K.",
      "D M K",
    ],
  },
  {
    label: "AIADMK Votes",
    abbreviations: ["AIADMK"],
    variants: [
      "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM",
      "ANNA DRAVIDA MUNNETRA KAZHAGAM",
      "A.I.A.D.M.K.",
      "A I A D M K",
    ],
  },
  {
    label: "BJP Votes",
    abbreviations: ["BJP"],
    variants: [
      "BHARATIYA JANATA PARTY",
      "BHARATIHA JANATA PARTY", // OCR typo variant
      "JANATA PARTY", // partial name
      "B.J.P.",
      "B J P",
    ],
  },
  {
    label: "NCP Votes",
    abbreviations: ["NCP"],
    variants: [
      "NATIONALIST CONGRESS PARTY",
      "N.C.P.",
      "N C P",
    ],
  },
  {
    label: "CONGRESS Votes",
    abbreviations: ["CONGRESS", "INC"],
    variants: [
      "INDIAN NATIONAL CONGRESS",
      "CONGRESS",
      "I.N.C.",
      "I N C",
    ],
  },

  // ── Alliance / medium parties ──
  {
    label: "PMK Votes",
    abbreviations: ["PMK"],
    variants: [
      "PATTALI MAKKAL KATCHI",
    ],
  },
  {
    label: "VCK Votes",
    abbreviations: ["VCK"],
    variants: [
      "VIDUTHALAI CHIRUTHAIGAL KATCHI",
    ],
  },
  {
    label: "NTK Votes",
    abbreviations: ["NTK"],
    variants: [
      "NAAM TAMILAR KATCHI",
      "NAAM TAMIZHAR KATCHI",
    ],
  },
  {
    label: "DMDK Votes",
    abbreviations: ["DMDK"],
    variants: [
      "DESIYA MURPOKKU DRAVIDA KAZHAGAM",
      "MURPOKKU DRAVIDA KAZHAGAM",
    ],
  },
  {
    label: "MDMK Votes",
    abbreviations: ["MDMK"],
    variants: [
      "MARUMALARCHI DRAVIDA MUNNETRA KAZHAGAM",
    ],
  },
  {
    label: "AMMK Votes",
    abbreviations: ["AMMK"],
    variants: [
      "AMMA MAKKAL MUNNETRA KAZHAGAM",
    ],
  },
  {
    label: "NDK Votes",
    abbreviations: ["NDK"],
    variants: [
      "NAADAALUM MAKKAL KATCHI",
    ],
  },

  // ── Left parties — CPI(M) BEFORE CPI to avoid false match ──
  {
    label: "CPI(M) Votes",
    abbreviations: ["CPIM", "CPI(M)", "CPM"],
    variants: [
      "COMMUNIST PARTY OF INDIA MARXIST",
    ],
  },
  {
    label: "CPI Votes",
    abbreviations: ["CPI"],
    variants: [
      "COMMUNIST PARTY OF INDIA",
    ],
  },

  // ── Congress allies / splinters ──
  {
    label: "TMC(M) Votes",
    abbreviations: ["TMC", "TMCM", "TMC(M)"],
    variants: [
      "TAMIL MAANILA CONGRESS",
      "TAMIL MAANILA CONGRESS MOOPANAR",
    ],
  },
  {
    label: "IUML Votes",
    abbreviations: ["IUML"],
    variants: [
      "INDIAN UNION MUSLIM LEAGUE",
    ],
  },
  {
    label: "AIFB Votes",
    abbreviations: ["AIFB"],
    variants: [
      "ALL INDIA FORWARD BLOC",
    ],
  },
  {
    label: "RPI(A) Votes",
    abbreviations: ["RPIA", "RPI(A)", "RPI"],
    variants: [
      "REPUBLICAN PARTY OF INDIA ATHAWALE",
      "REPUBLICAN PARTY OF INDIA",
    ],
  },

  // ── Smaller / regional parties ──
  {
    label: "BSP Votes",
    abbreviations: ["BSP"],
    variants: [
      "BAHUJAN SAMAJ PARTY",
    ],
  },
  {
    label: "MNM Votes",
    abbreviations: ["MNM"],
    variants: [
      "MAKKAL NEEDHI MAIAM",
    ],
  },
  {
    label: "IJK Votes",
    abbreviations: ["IJK"],
    variants: [
      "INDIA JANANAYAKA KATCHI",
      "INDIYA JANANAYAKA KATCHI",
      "INDIA JANAYAKA KATCHI",
      "INDIYA JANAYAKA KATCHI",
    ],
  },
  {
    label: "KMDK Votes",
    abbreviations: ["KMDK"],
    variants: [
      "KONGUNADU MAKKAL DESIA KATCHI",
      "KONGUNADU MAKKAL DESIYA KATCHI",
    ],
  },
  {
    label: "MMK Votes",
    abbreviations: ["MMK"],
    variants: [
      "MANITHANEYA MAKKAL KATCHI",
    ],
  },
  {
    label: "SDPI Votes",
    abbreviations: ["SDPI"],
    variants: [
      "SOCIAL DEMOCRATIC PARTY OF INDIA",
    ],
  },
  {
    label: "PT Votes",
    abbreviations: ["PT"],
    variants: [
      "PUTHIYA TAMILAGAM",
    ],
  },
  {
    label: "AIMIM Votes",
    abbreviations: ["AIMIM"],
    variants: [
      "ALL INDIA MAJLIS E ITTEHADUL MUSLIMEEN",
      "MAJLIS E ITTEHADUL MUSLIMEEN",
    ],
  },
  {
    label: "TMK Votes",
    abbreviations: ["TMK"],
    variants: [
      "TAMILAGA MAKKAL KATCHI",
    ],
  },

  // ── Special entries (must be AFTER parties with overlapping words) ──
  {
    label: "IND Votes",
    abbreviations: ["IND", "INDEPENDENT"],
    variants: [
      "INDEPENDENT",
    ],
  },
  {
    label: "NOTA Votes",
    abbreviations: ["NOTA"],
    variants: [
      "NONE OF THE ABOVE",
    ],
  },
];

// ──────────────────────────────────────────────
// Administrative / structural column definitions
// These are non-party columns commonly found in
// election result PDFs with many naming variants.
// ──────────────────────────────────────────────

type ColumnDefinition = {
  label: string;
  /** Column type for badge display */
  type: "identifier" | "location" | "count" | "special";
  variants: string[];
  abbreviations?: string[];
};

const ADMIN_COLUMNS: ColumnDefinition[] = [
  {
    label: "Polling Station No.",
    type: "identifier",
    abbreviations: ["PSNO", "PS NO"],
    variants: [
      "POLLING STATION NO",
      "POLLING STATION NUMBER",
      "POLLING STATION NO.",
      "PS NO",
      "PS NO.",
      "PSNO",
      "P.S. NO",
      "P.S.NO",
      "P S NO",
      "BOOTH NO",
      "BOOTH NO.",
      "BOOTH NUMBER",
      "BOOTH",
      "POLLING BOOTH NO",
      "POLLING BOOTH NUMBER",
      "POLLING BOOTH",
      "STATION NO",
      "STATION NUMBER",
      "STN NO",
    ],
  },
  {
    label: "Polling Station Name",
    type: "location",
    variants: [
      "POLLING STATION NAME",
      "POLLING STATION LOCATION",
      "PS NAME",
      "STATION NAME",
      "BOOTH NAME",
      "BOOTH LOCATION",
      "POLLING BOOTH NAME",
      "LOCATION",
      "BUILDING NAME",
      "NAME OF POLLING STATION",
      "NAME OF THE POLLING STATION",
    ],
  },
  {
    label: "SL. NO.",
    type: "identifier",
    abbreviations: ["SLNO", "SL NO"],
    variants: [
      "SL NO",
      "SL. NO",
      "SL. NO.",
      "SL.NO",
      "SL.NO.",
      "S NO",
      "S. NO",
      "S.NO",
      "SERIAL NO",
      "SERIAL NO.",
      "SERIAL NUMBER",
      "SR NO",
      "SR. NO",
      "SR.NO",
    ],
  },
  {
    label: "AC NO.",
    type: "identifier",
    abbreviations: ["ACNO", "AC NO"],
    variants: [
      "AC NO",
      "AC NO.",
      "AC.NO",
      "AC.NO.",
      "A.C. NO",
      "ASSEMBLY CONSTITUENCY NO",
      "ASSEMBLY CONSTITUENCY NUMBER",
      "CONSTITUENCY NO",
      "CONSTITUENCY NUMBER",
    ],
  },
  {
    label: "Total Valid Votes",
    type: "count",
    variants: [
      "TOTAL VALID VOTES",
      "TOTAL VOTES",
      "TOTAL VALID VOTES POLLED",
      "TOTAL VOTES POLLED",
      "VALID VOTES",
      "VOTES POLLED",
      "TOTAL",
    ],
  },
  {
    label: "Rejected Votes",
    type: "count",
    variants: [
      "REJECTED VOTES",
      "REJECTED",
      "INVALID VOTES",
      "REJECTED BALLOT",
      "REJECTED BALLOTS",
      "NO OF REJECTED VOTES",
    ],
  },
  {
    label: "Tendered Votes",
    type: "count",
    variants: [
      "TENDERED VOTES",
      "TENDERED",
      "NO OF TENDERED VOTES",
    ],
  },
  {
    label: "Total Electors",
    type: "count",
    variants: [
      "TOTAL ELECTORS",
      "ELECTORS",
      "NO OF ELECTORS",
      "TOTAL VOTERS",
      "VOTERS",
      "REGISTERED VOTERS",
    ],
  },
];

// Build admin column index (simpler — no reversal needed for English admin terms)
const ADMIN_INDEX = ADMIN_COLUMNS.map((col) => {
  const variantNorms = col.variants.map((v) => normalizeForMatch(v));
  const variantNoSpace = col.variants.map((v) => normalizeNoSpace(v));
  const abbr = (col.abbreviations ?? []).map((a) => normalizeForMatch(a));
  return { def: col, variantNorms, variantNoSpace, abbr };
});

export type ColumnMatch = {
  label: string;
  confidence: number;
  type: "party" | "identifier" | "location" | "count" | "special";
};

/**
 * Match an admin/structural column header.
 * Returns null if no confident match is found.
 */
function matchAdminColumn(header: string): ColumnMatch | null {
  const raw = header ?? "";
  const norm = normalizeForMatch(raw);
  const noSpace = normalizeNoSpace(raw);
  if (!norm) return null;

  let best: ColumnMatch | null = null;

  for (const col of ADMIN_INDEX) {
    let score = 0;

    // Abbreviation exact match
    for (const ab of col.abbr) {
      if (norm === ab || noSpace === ab.replace(/\s+/g, "")) {
        score = Math.max(score, 1.0);
      }
    }

    // Variant matching
    for (let j = 0; j < col.variantNorms.length; j++) {
      const v = col.variantNorms[j];
      const vns = col.variantNoSpace[j];
      if (norm === v || noSpace === vns) score = Math.max(score, 1.0);
      if (norm.includes(v) || v.includes(norm)) score = Math.max(score, 0.92);
    }

    if (score > 0 && (!best || score > best.confidence)) {
      best = { label: col.def.label, confidence: score, type: col.def.type };
    }
  }

  if (!best || best.confidence < 0.85) return null;
  return best;
}

/**
 * Unified column matcher — tries admin columns first, then party labels.
 * Use this from the UI to get a clean display label for any column header.
 */
export function matchColumnLabel(header: string): ColumnMatch | null {
  // Try admin column match first (exact/known names, no reversal needed)
  const admin = matchAdminColumn(header);
  if (admin) return admin;

  // Fall back to party label matching
  const party = matchPartyLabel(header);
  if (party) return { ...party, type: "party" };

  return null;
}

// ──────────────────────────────────────────────
// Build search index — auto-generate ALL reversal
// forms for every variant so we don't need to
// hardcode reversed strings.
// ──────────────────────────────────────────────

const PARTY_INDEX = PARTIES.map((p) => {
  const allVariantNorms = new Set<string>();
  for (const v of p.variants) {
    const norm = normalizeForMatch(v);
    if (!norm) continue;
    allVariantNorms.add(norm);
    allVariantNorms.add(reverseWords(norm));
    allVariantNorms.add(reverseEachWord(norm));
    allVariantNorms.add(reverseChars(norm));
    // Combined: reverse word order, then reverse each word's characters
    allVariantNorms.add(reverseEachWord(reverseWords(norm)));
  }

  const expandedVariants = Array.from(allVariantNorms);
  const variantNoSpace = expandedVariants.map((v) => v.replace(/\s+/g, ""));
  const variantTokenSets = expandedVariants.map((v) => tokenSet(v));
  const abbr = (p.abbreviations ?? []).map((a) => normalizeForMatch(a));
  return {
    def: p,
    variantNorms: expandedVariants,
    variantNoSpace,
    variantTokenSets,
    abbr,
  };
});

/**
 * Best-effort match a raw Excel header to one of the configured party labels.
 *
 * High precision by default:
 * - Only returns a match if confidence >= 0.85
 * - Otherwise returns null (caller should show original header)
 */
export function matchPartyLabel(header: string): PartyMatch | null {
  const raw = header ?? "";
  const tail = extractTailAfterDash(raw);

  const candidates = new Set<string>();
  for (const s of [raw, tail]) {
    const n = normalizeForMatch(s);
    if (!n) continue;
    candidates.add(n);
    candidates.add(reverseWords(n));
    candidates.add(reverseEachWord(n));
    candidates.add(reverseChars(n));
    // Combined reversal: handles cases where both word order
    // AND each word's characters are reversed
    candidates.add(reverseEachWord(reverseWords(n)));
  }

  const candidateList = Array.from(candidates);
  const candidateNoSpace = candidateList.map((c) => c.replace(/\s+/g, ""));
  const candidateTokenSets = candidateList.map((c) => tokenSet(c));

  let best: PartyMatch | null = null;

  for (const p of PARTY_INDEX) {
    let score = 0;

    // Abbreviation match (very strong signal)
    if (p.abbr.length) {
      for (const c of candidateList) {
        for (const ab of p.abbr) {
          if (!ab) continue;
          const abUpper = ab.toUpperCase();
          const cUpper = c.toUpperCase();

          // Exact match (highest priority)
          if (cUpper === abUpper) {
            score = Math.max(score, 1.0);
          }
          // For short abbreviations (≤3 chars), require word boundary to avoid false positives
          // e.g., "PT" should not match inside "PARTY", "IND" should not match inside "INDIA"
          else if (abUpper.length <= 3) {
            const wordBoundaryRegex = new RegExp(`\\b${abUpper}\\b`, "i");
            if (wordBoundaryRegex.test(cUpper)) {
              score = Math.max(score, 0.98);
            }
          }
          // For longer abbreviations, allow substring match with word boundary preference
          else if (cUpper.includes(abUpper)) {
            const wordBoundaryRegex = new RegExp(`\\b${abUpper}\\b`, "i");
            if (wordBoundaryRegex.test(cUpper)) {
              score = Math.max(score, 0.98);
            } else {
              score = Math.max(score, 0.85);
            }
          }
        }
      }
    }

    // Exact / no-space exact against any variant (including auto-generated reversed forms)
    for (let i = 0; i < candidateList.length; i++) {
      const c = candidateList[i];
      const cns = candidateNoSpace[i];
      for (let j = 0; j < p.variantNorms.length; j++) {
        const v = p.variantNorms[j];
        const vns = p.variantNoSpace[j];
        if (!v) continue;
        if (c === v || cns === vns) score = Math.max(score, 1.0);
        if (c.includes(v) || v.includes(c)) score = Math.max(score, 0.92);
      }
    }

    // Token similarity against variants
    for (let i = 0; i < candidateTokenSets.length; i++) {
      const cset = candidateTokenSets[i];
      for (const vset of p.variantTokenSets) {
        const jac = jaccard(cset, vset);
        // Require at least 2 overlapping tokens for multiword parties to avoid false positives
        let overlap = 0;
        for (const t of cset) if (vset.has(t)) overlap++;
        if (overlap >= 2) score = Math.max(score, jac);
      }
    }

    if (!best || score > best.confidence) {
      best = { label: p.def.label, confidence: score };
    }
  }

  // High precision threshold to avoid mislabeling
  const importantParties = [
    "DMK Votes", "AIADMK Votes", "BJP Votes", "CONGRESS Votes",
    "PMK Votes", "VCK Votes", "NTK Votes", "AMMK Votes", "DMDK Votes",
  ];
  const isImportantParty = best && importantParties.includes(best.label);
  const minConfidence = isImportantParty ? 0.90 : 0.85;

  if (!best || best.confidence < minConfidence) return null;
  return best;
}
