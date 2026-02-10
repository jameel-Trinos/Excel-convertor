/**
 * Tamil Nadu Election Alliance Configuration
 *
 * Keys: main party abbreviations
 * Values: alliance party abbreviations
 *
 * These abbreviations are matched against column headers using
 * matchPartyLabel() from partyHeaderMapper.ts
 */

/** Loksabha alliance configuration (default) */
export const ALLIANCE_CONFIG: Record<string, { color: string; allies: string[] }> = {
  DMK: {
    color: "#e53e3e", // red
    allies: ["KMDK", "INC", "CPI", "CPI(M)", "VCK", "IUML", "MDMK"],
  },
  BJP: {
    color: "#ed8936", // orange
    allies: ["IJK", "IMKMK", "PNK", "TMMK", "PMK", "TMC(M)", "AMMK"],
  },
  AIADMK: {
    color: "#38a169", // green
    allies: ["PT", "SDPI", "DMDK"],
  },
};

/** Alias for clarity */
export const LOKSABHA_ALLIANCE_CONFIG = ALLIANCE_CONFIG;

/** Assembly alliance configuration */
export const ASSEMBLY_ALLIANCE_CONFIG: Record<string, { color: string; allies: string[] }> = {
  AIADMK: {
    color: "#38a169", // green
    allies: [
      "TMC(M)",
      "PERUNTHALAIVAR MAKKAL KATCHI",
      "TMMK",
      "MOOVENDAR MUNNETRA KAZHAGAM",
      "ALL INDIA MOOVENDAR MUNNANI KAZHAGAM",
      "PURATCHI BHARATHAM KATCHI",
      "PASUMPON DESIYA KAZHAGAM",
      "PMK",
      "BJP",
    ],
  },
  DMK: {
    color: "#e53e3e", // red
    allies: [
      "MDMK",
      "KMDK",
      "MMK",
      "AIFB",
      "TAMIZHAGA VAZHVURIMAI KATCHI",
      "MAKKAL VIDUTHALAI KATCHI",
      "AATHI THAMIZHAR PERAVAI",
      "INC",
      "VCK",
      "CPI",
      "CPI(M)",
      "IUML",
    ],
  },
};

/** All main party keys */
export const MAIN_PARTIES = Object.keys(ALLIANCE_CONFIG) as Array<keyof typeof ALLIANCE_CONFIG>;
