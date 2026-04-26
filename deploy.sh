#!/bin/bash
# ═══════════════════════════════════════════════════
#  deploy.sh — Upload file BBM Tracker ke GitHub
#  Cara pakai:
#    chmod +x deploy.sh
#    ./deploy.sh
# ═══════════════════════════════════════════════════

# Sesuaikan dengan akun dan nama repo Anda
GITHUB_USER="ditolabs"
REPO="fuelcalc"
BRANCH="main"
FILES=("index.html" "manifest.json" "sw.js" "icon.svg")

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

# Set standard API Headers untuk GitHub API v3
HEADER_AUTH="Authorization: Bearer $TOKEN"
HEADER_ACCEPT="Accept: application/vnd.github+json"
HEADER_VERSION="X-GitHub-Api-Version: 2022-11-28"

# ── Cek token valid ──
echo "🔑 Mengecek token..."
USER_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "$HEADER_AUTH" -H "$HEADER_ACCEPT" -H "$HEADER_VERSION" \
  https://api.github.com/user)

if [ "$USER_CHECK" != "200" ]; then
  echo "❌ Token tidak valid atau tidak punya izin (HTTP $USER_CHECK)."
  exit 1
fi
echo "✅ Token valid."

# ── Cek repo ada ──
echo "📦 Mengecek repo $GITHUB_USER/$REPO..."
REPO_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "$HEADER_AUTH" -H "$HEADER_ACCEPT" -H "$HEADER_VERSION" \
  https://api.github.com/repos/$GITHUB_USER/$REPO)

if [ "$REPO_CHECK" = "404" ]; then
  echo "⚠️  Repo belum ada. Membuat repo baru..."
  CREATE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "$HEADER_AUTH" -H "$HEADER_ACCEPT" -H "$HEADER_VERSION" \
    -d "{\"name\":\"$REPO\",\"description\":\"BBM Tracker Estimator\",\"private\":false,\"auto_init\":true}" \
    https://api.github.com/user/repos)
  
  STATUS=$(echo "$CREATE" | tail -1)
  if [ "$STATUS" != "201" ]; then
    echo "❌ Gagal membuat repo (HTTP $STATUS)."
    exit 1
  fi
  echo "✅ Repo berhasil dibuat."
  sleep 3 # Waktu tunggu agar GitHub selesai inisialisasi repo
fi

# ── Upload setiap file ──
echo ""
echo "📤 Mengupload file..."
FAIL=0

for FILE in "${FILES[@]}"; do
  if [ ! -f "$FILE" ]; then
    echo "  ⚠️  $FILE tidak ditemukan di folder lokal, dilewati."
    continue
  fi

  # Encode file ke base64 (tanpa newline untuk menghindari JSON error)
  CONTENT=$(base64 -w 0 "$FILE" 2>/dev/null || base64 "$FILE" | tr -d '\n')

  # Dapatkan SHA dari file yang sudah ada (jika ada, untuk proses update)
  EXISTING=$(curl -s \
    -H "$HEADER_AUTH" -H "$HEADER_ACCEPT" -H "$HEADER_VERSION" \
    https://api.github.com/repos/$GITHUB_USER/$REPO/contents/$FILE)

  SHA=$(echo "$EXISTING" | grep '"sha"' | head -1 | sed 's/.*"sha": *"\([^"]*\)".*/\1/')

  # Susun JSON payload
  if [ -n "$SHA" ]; then
    PAYLOAD="{\"message\":\"Update $FILE via script\",\"content\":\"$CONTENT\",\"sha\":\"$SHA\",\"branch\":\"$BRANCH\"}"
  else
    PAYLOAD="{\"message\":\"Add $FILE via script\",\"content\":\"$CONTENT\",\"branch\":\"$BRANCH\"}"
  fi

  # Upload / Update
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "$HEADER_AUTH" -H "$HEADER_ACCEPT" -H "$HEADER_VERSION" \
    -d "$PAYLOAD" \
    https://api.github.com/repos/$GITHUB_USER/$REPO/contents/$FILE)

  if [ "$RESULT" = "200" ] || [ "$RESULT" = "201" ]; then
    echo "  ✅ $FILE berhasil di-push."
  else
    echo "  ❌ $FILE gagal (HTTP $RESULT)."
    FAIL=1
  fi
done

# ── Aktifkan GitHub Pages (jika belum aktif) ──
echo ""
echo "🌐 Mengecek/Mengaktifkan GitHub Pages..."
PAGES=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "$HEADER_AUTH" -H "$HEADER_ACCEPT" -H "$HEADER_VERSION" \
  -d "{\"source\":{\"branch\":\"$BRANCH\",\"path\":\"/\"}}" \
  https://api.github.com/repos/$GITHUB_USER/$REPO/pages)

if [ "$PAGES" = "201" ]; then
  echo "✅ GitHub Pages diaktifkan."
elif [ "$PAGES" = "409" ]; then
  echo "✅ GitHub Pages sudah aktif sebelumnya."
else
  echo "⚠️  (HTTP $PAGES) Anda mungkin perlu mengaktifkan Pages secara manual di Pengaturan Repo GitHub Anda."
fi

# ── Selesai ──
echo ""
if [ "$FAIL" = "0" ]; then
  echo "🎉 Semua file berhasil dideploy ke GitHub!"
else
  echo "⚠️  Ada file yang gagal diupload. Silakan cek pesan error di atas."
fi

echo ""
echo "🔗 Cek aplikasi Anda di: https://$GITHUB_USER.github.io/$REPO/"
echo "   (Beri waktu sekitar 1-2 menit untuk GitHub memproses perubahan)"
echo ""
