#!/bin/sh
# Pulls the four sources into a scratch folder and copies them in. Then run tools/convert.py and review.
#   tools/update-sources.sh <scratch dir>
set -e
here=$(cd "$(dirname "$0")/.." && pwd)
w=${1:?scratch dir}
mkdir -p "$w"
get() { # repo dir path
  if [ -d "$w/$2" ]; then git -C "$w/$2" pull -q; else git clone -q --depth 1 --filter=blob:none --sparse "$1" "$w/$2" && git -C "$w/$2" sparse-checkout set "$3"; fi
  echo "$2: $(git -C "$w/$2" rev-parse HEAD)"
}
get https://github.com/project64/project64 pj64 Config/Cheats
get https://github.com/Rosalie241/RMG rmg Data/Cheats/Custom
get https://github.com/libretro/libretro-database lrdb "cht/Nintendo - Nintendo 64"
get https://github.com/mupen64plus-ae/mupen64plus-ae fz app/src/main/assets/mupen64plus_data
get https://github.com/mupen64plus/mupen64plus-core up data
rm -f "$here"/sources/project64/*.cht "$here"/sources/rmg-custom/*.cht "$here"/sources/libretro/*.cht
cp "$w"/pj64/Config/Cheats/*.cht "$here/sources/project64/"
cp "$w"/rmg/Data/Cheats/Custom/*.cht "$here/sources/rmg-custom/"
cp "$w/lrdb/cht/Nintendo - Nintendo 64/"*.cht "$here/sources/libretro/"
python "$here/tools/extract-retroben.py" "$w/fz/app/src/main/assets/mupen64plus_data/mupencheat.default" "$w/up/data/mupencheat.txt"
cp "$w/up/data/mupen64plus.ini" "$here/tools/mupen64plus.ini"
echo "Now update each SOURCE.md's commit, run tools/convert.py and review the diff."
