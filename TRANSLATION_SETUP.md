# Translation Service Setup Guide

This document explains how the Excel translation feature works using Google Translate.

## Overview

The translation service now uses **Google Translate** via the `deep-translator` Python library for simple, reliable translations.

**Supported Languages:**
- **Tamil** (தமிழ்)
- **Hindi** (हिंदी)
- **English**

## Installation

### Step 1: Install deep-translator

```bash
cd backend
source ../.venv/bin/activate
pip install deep-translator==1.11.4
```

### Step 2: Verify Installation

The translation service will automatically load when the backend starts. No API keys or model downloads required!

## How It Works

### Translation Process

1. **Upload PDF** → Convert to Excel
2. **Select Language** → Choose Tamil, Hindi, or English from dropdown
3. **Translate** → Google Translate processes the content
4. **Download** → Get your translated Excel file

### What Gets Translated

The service intelligently translates:
- Headers (Booth, Constituency, Candidate, etc.)
- Text content in cells
- Location names
- Party names (with special handling for abbreviations)

### What Stays Unchanged

The service preserves:
- **Numbers**: 123, 45.67, 1,234
- **IDs and Codes**: ABC123, PS001
- **Party Abbreviations**: DMK, BJP, AIADMK, NOTA, etc.
- **Phone Numbers**: 10-12 digit numbers
- **Pin Codes**: 6-digit codes
- **Dates**: Various date formats
- **Percentages**: 20%, 45.5%
- **URLs and Emails**
- **Formulas**: Excel formulas like =SUM()
- **Formatting**: Colors, fonts, borders, merged cells

### Pre-Cached Common Terms

For consistency, common election terms use a built-in dictionary:

**Tamil Translations:**
- Polling Station → வாக்குச்சாவடி
- Constituency → தொகுதி
- Candidate → வேட்பாளர்
- Total → மொத்தம்
- Valid Votes → செல்லுபடியான வாக்குகள்
- [See full list in backend/app/translation_service.py]

**Hindi Translations:**
- Polling Station → मतदान केंद्र
- Constituency → निर्वाचन क्षेत्र
- Candidate → उम्मीदवार
- Total → कुल
- Valid Votes → वैध मत
- [See full list in backend/app/translation_service.py]

## User Interface

### Language Selector Dropdown

The translation feature provides a dropdown menu with three options:
- 🇮🇳 **தமிழ் Tamil**
- 🇮🇳 **हिंदी Hindi**
- 🇬🇧 **English**
- 📄 **English (Original)** - Return to untranslated version

### Features:
- **Visual Indicators**: Shows "✓ Available" for already-translated versions
- **Progress Bar**: Real-time progress during translation
- **Cancel Button**: Stop translation in progress
- **Error Handling**: Clear error messages if translation fails

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/translate/start` | POST | Start translation (body: `{task_id, target_lang}`) |
| `/api/translate/progress/{translate_task_id}` | GET | SSE stream for real-time progress |
| `/api/translate/status/{task_id}` | GET | Check availability of Tamil/Hindi/English versions |
| `/api/translate/cancel/{translate_task_id}` | POST | Cancel ongoing translation |
| `/api/download/{task_id}/{language}` | GET | Download translated Excel file |

### Example Request

```bash
curl -X POST http://localhost:8000/api/translate/start \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "abc-123",
    "target_lang": "tamil"
  }'
```

## Advantages of Google Translate

### Simple Setup
- ✅ No model downloads (IndicTrans2 was 200-300MB)
- ✅ No GPU/CPU optimization needed
- ✅ No dependency conflicts (torch, numpy, transformers)
- ✅ Works out-of-the-box

### Reliable
- ✅ Consistent output (unlike MarianMT which could output Telugu/Kannada/Tamil randomly)
- ✅ Battle-tested translation quality
- ✅ Automatic language detection
- ✅ Fast translation speed

### Multiple Languages
- ✅ Easy to add more languages (just update LANGUAGE_CODES)
- ✅ No additional model downloads per language
- ✅ Consistent quality across languages

## Limitations

1. **Internet Required**: Google Translate requires internet connection
2. **Rate Limiting**: May hit rate limits with very large files (use caching to mitigate)
3. **Free Service**: Using the free deep-translator library (not official Google Cloud Translation API)

## Configuration

### Adding More Languages

To add a new language (e.g., Telugu):

1. **Update `translation_service.py`**:
```python
LANGUAGE_CODES = {
    "tamil": "ta",
    "hindi": "hi",
    "telugu": "te",  # Add Telugu
    "english": "en",
}

COMMON_TRANSLATIONS = {
    "telugu": {
        "Polling Station": "ఓటింగ్ స్టేషన్",
        # ... add more
    }
}
```

2. **Update `models.py`**:
```python
target_lang: Literal["tamil", "hindi", "telugu", "english"]
```

3. **Update frontend** `types/index.ts`, `translation-api.ts`, and `TranslationToggle.tsx`

## Troubleshooting

### Error: "Missing deep-translator library"
**Solution:**
```bash
pip install deep-translator==1.11.4
```

### Error: "Translation timeout"
**Cause:** Network issue or rate limiting
**Solution:**
- Check internet connection
- Wait a few minutes and try again
- Break large files into smaller ones

### Error: "Connection to translation server lost"
**Cause:** Backend crashed or network issue
**Solution:**
- Check backend logs: `docker-compose logs -f backend`
- Restart backend: `docker-compose restart backend`

### Slow Translation
**Cause:** Large file or slow network
**Solution:**
- Translation speed depends on internet speed
- Consider breaking very large files into smaller batches

## Comparison: IndicTrans2 vs Google Translate

| Feature | IndicTrans2 (Old) | Google Translate (New) |
|---------|------------------|----------------------|
| Setup Complexity | High (torch, numpy, transformers) | Low (pip install) |
| Model Size | 200-300MB | None (API-based) |
| Dependencies | 8+ packages | 1 package |
| Tamil Quality | Excellent | Very Good |
| Hindi Support | Yes | Yes |
| Speed | Fast (after loading) | Fast |
| Offline Support | Yes | No |
| Consistency | High | High |
| Memory Usage | ~1GB | Minimal |

## Migration Notes

### Removed Dependencies
The following packages are NO LONGER required:
- ❌ `transformers`
- ❌ `sentencepiece`
- ❌ `torch`
- ❌ `safetensors`
- ❌ `accelerate`
- ❌ `IndicTransToolkit`

### API Changes
- Backend: Changed from `direction: "to_tamil"` to `target_lang: "tamil"`
- Frontend: Dropdown replaces toggle button
- Added Hindi language support

---

**Last Updated:** February 5, 2026
**Project:** PDF to Excel Converter with Multi-Language Translation
**Translation Engine:** Google Translate (deep-translator 1.11.4)
