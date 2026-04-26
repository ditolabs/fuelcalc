#!/bin/bash
# ═══════════════════════════════════════════════════
#  deploy.sh — Upload file BBM Tracker ke GitHub
#  Cara pakai:
#    chmod +x deploy.sh   (sekali saja)
#    ./deploy.sh
# ═══════════════════════════════════════════════════

GITHUB_USER="ShadowSoldiers"
REPO="kalkulator-bbm"
BRANCH="main"
FILES=("index.html" "manifest.json" "sw.js" "icon.svg")

# ── Minta token ──
echo ""
echo "╔══════════════════════════════════════╗"
echo "║       BBM Tracker — Deploy Tool      ║"
echo "╚══════════════════════════════════════╝"
echo ""
read -rsp "Paste GitHub Personal Access Token: " TOKEN
echo ""

if [ -z "$TOKEN" ]; then
  echo "❌ Token tidak boleh kosong."
  exit 1
fi

# ── Cek token valid ──
echo "🔑 Mengecek token..."
USER_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/user)

if [ "$USER_CHECK" != "200" ]; then
  echo "❌ Token tidak valid atau tidak punya akses (HTTP $USER_CHECK)."
  exit 1
fi
echo "✅ Token valid."

# ── Cek repo ada ──
echo "📦 Mengecek repo $GITHUB_USER/$REPO..."
REPO_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/$GITHUB_USER/$REPO 2>/dev/null || \
  curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$GITHUB_USER/$REPO)

if [ "$REPO_CHECK" = "404" ]; then
  echo "⚠️  Repo belum ada. Membuat repo baru..."
  CREATE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$REPO\",\"description\":\"BBM Tracker PWA\",\"private\":false,\"auto_init\":true}" \
    https://api.github.com/user/repos)
  STATUS=$(echo "$CREATE" | tail -1)
  if [ "$STATUS" != "201" ]; then
    echo "❌ Gagal membuat repo (HTTP $STATUS)."
    exit 1
  fi
  echo "✅ Repo berhasil dibuat."
  sleep 2 # tunggu GitHub siapkan repo
fi

# ── Upload setiap file ──
echo ""
echo "📤 Mengupload file..."
FAIL=0

for FILE in "${FILES[@]}"; do
  if [ ! -f "$FILE" ]; then
    echo "  ⚠️  $FILE tidak ditemukan, dilewati."
    continue
  fi

  # Encode file ke base64
  CONTENT=$(base64 -w 0 "$FILE" 2>/dev/null || base64 "$FILE")

  # Cek apakah file sudah ada (untuk dapat SHA-nya)
  EXISTING=$(curl -s \
    -H "Authorization: token $TOKEN" \
    https://api.github.com/repos/$GITHUB_USER/$REPO/contents/$FILE)

  SHA=$(echo "$EXISTING" | grep '"sha"' | head -1 | sed 's/.*"sha": *"\([^"]*\)".*/\1/')

  # Susun payload
  if [ -n "$SHA" ]; then
    PAYLOAD="{\"message\":\"update $FILE\",\"content\":\"$CONTENT\",\"sha\":\"$SHA\",\"branch\":\"$BRANCH\"}"
  else
    PAYLOAD="{\"message\":\"add $FILE\",\"content\":\"$CONTENT\",\"branch\":\"$BRANCH\"}"
  fi

  # Upload
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    https://api.github.com/repos/$GITHUB_USER/$REPO/contents/$FILE)

  if [ "$RESULT" = "200" ] || [ "$RESULT" = "201" ]; then
    echo "  ✅ $FILE"
  else
    echo "  ❌ $FILE (HTTP $RESULT)"
    FAIL=1
  fi
done

# ── Aktifkan GitHub Pages (jika belum) ──
echo ""
echo "🌐 Mengaktifkan GitHub Pages..."
PAGES=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"source\":{\"branch\":\"$BRANCH\",\"path\":\"/\"}}" \
  https://api.github.com/repos/$GITHUB_USER/$REPO/pages)

if [ "$PAGES" = "201" ]; then
  echo "✅ GitHub Pages diaktifkan."
elif [ "$PAGES" = "409" ]; then
  echo "✅ GitHub Pages sudah aktif sebelumnya."
else
  echo "⚠️  Pages mungkin perlu diaktifkan manual di Settings → Pages (HTTP $PAGES)."
fi

# ── Selesai ──
echo ""
if [ "$FAIL" = "0" ]; then
  echo "🎉 Semua file berhasil diupload!"
else
  echo "⚠️  Beberapa file gagal diupload. Coba lagi."
fi

echo ""
echo "🔗 URL app: https://$GITHUB_USER.github.io/$REPO/"
echo "   (GitHub Pages butuh ~1-2 menit untuk deploy)"
echo ""
