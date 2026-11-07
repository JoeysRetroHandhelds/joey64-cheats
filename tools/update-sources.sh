#!/bin/sh
# Pulls the four sources into a scratch folder and copies them in. Then run tools/convert.py and review.
#   tools/update-sources.sh <scratch dir>
set -e
here=$(cd "$(dirname "$0")/.." && pwd)
w=${1:?scratch dir}
mkdir -p "$w"
get() { # repo dir path [path...]
  r=$1; d=$2; shift 2
  if [ -d "$w/$d" ]; then git -C "$w/$d" pull -q; else git clone -q --depth 1 --filter=blob:none --sparse "$r" "$w/$d" && git -C "$w/$d" sparse-checkout set "$@"; fi
  echo "$d: $(git -C "$w/$d" rev-parse HEAD)"
}
stamp() { # SOURCE.md dir: writes that clone's commit and date into its "commit <sha> (<date>)"
  sha=$(git -C "$w/$2" rev-parse HEAD); day=$(git -C "$w/$2" log -1 --format=%cs)
  sed -i -E "s/commit [0-9a-f]{40} \([0-9-]+\)/commit $sha ($day)/" "$here/sources/$1/SOURCE.md"
}
get https://github.com/project64/project64 pj64 Config/Cheats Config/Enhancements
get https://github.com/Rosalie241/RMG rmg Data/Cheats/Custom
get https://github.com/libretro/libretro-database lrdb "cht/Nintendo - Nintendo 64"
get https://github.com/mupen64plus-ae/mupen64plus-ae fz app/src/main/assets/mupen64plus_data
get https://github.com/mupen64plus/mupen64plus-core up data
rm -f "$here"/sources/project64/*.cht "$here"/sources/rmg-custom/*.cht "$here"/sources/libretro/*.cht
rm -f "$here"/sources/project64/enhancements/*.enh
cp "$w"/pj64/Config/Cheats/*.cht "$here/sources/project64/"
mkdir -p "$here/sources/project64/enhancements"
cp "$w"/pj64/Config/Enhancements/*.enh "$here/sources/project64/enhancements/"
cp "$w"/rmg/Data/Cheats/Custom/*.cht "$here/sources/rmg-custom/"
cp "$w/lrdb/cht/Nintendo - Nintendo 64/"*.cht "$here/sources/libretro/"
python "$here/tools/extract-retroben.py" "$w/fz/app/src/main/assets/mupen64plus_data/mupencheat.default" "$w/up/data/mupencheat.txt"
cp "$w/up/data/mupen64plus.ini" "$here/tools/mupen64plus.ini"
cp "$w/pj64/Config/Project64.rdb" "$here/tools/project64.rdb"
stamp project64 pj64; stamp rmg-custom rmg; stamp libretro lrdb
sed -i -E "s/\(commit [0-9a-f]{40}\) by/(commit $(git -C "$w/up" rev-parse HEAD)) by/" "$here/sources/fz-retroben/SOURCE.md"
stamp fz-retroben fz
echo "Now run tools/convert.py and review the diff."
