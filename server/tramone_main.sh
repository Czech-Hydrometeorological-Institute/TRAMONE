#!/bin/bash
#set -euo pipefail
TRAMONE_folder="$HOME/TRAMONE"
source "$TRAMONE_folder/tramone.cfg"

########################################################################
# subroutines


wind_gridding() {
	#Rscript for wind file parsing
	exec 4>"${TRAMONE_folder}/.wind_text_files_lock"
		flock -x 4
		Rscript ${TRAMONE_folder}/wind_preparation.R ${TRAMONE_folder}/wind.txt ${TRAMONE_folder}/meteo_sites.txt ${TRAMONE_folder} ${TRAMONE_folder}/wind_AIM.txt ${TRAMONE_folder}/meteo_sites_AIM.txt
		flock -s 4
		wind_head=$(head "${TRAMONE_folder}/wind.csv" -n 3)
		wind_tail=$(tail "${TRAMONE_folder}/wind.csv" -n 3)
		flock -u 4
	exec 4>&-
	# if wind file has changed, prepare new wind layers and grid the wind field
	if [[ "$wind_head" != "$wind_head_prev" || "$wind_tail" != "$wind_tail_prev" ]]; then
		wind_head_for_grid=$wind_head
		wind_tail_for_grid=$wind_tail
		flock -x "${TRAMONE_folder}/.wind_GIS_layers_lock" grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.in.ascii -z input=${TRAMONE_folder}/wind.csv output=wind sep="," skip=1 x=6 y=7 z=8 columns="EG_GH_ID varchar(8),wd integer,ws real,u_wind real,v_wind real,x double,y double,elevation integer,date varchar(50)"
		range_x=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.univar map=wind column=x | grep "Range:" | awk '{print $2}')
		range_y=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.univar map=wind column=y | grep "Range:" | awk '{print $2}')
		range_z=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.univar map=wind column=elevation | grep "Range:" | awk '{print $2}')
		if (( $(echo "$range_x > $range_y" | bc -l) )); then
			#scale_xy_z=$(echo "scale=6; $range_x / $range_z * 0.25"|bc)
			scale_xy_z=$(echo "scale=6; $range_x / $range_z * 0.25"|bc)
		else
			#scale_xy_z=$(echo "scale=6; $range_y / $range_z * 0.25"|bc)
			scale_xy_z=$(echo "scale=6; $range_y / $range_z * 0.25"|bc)
		fi
		#kill any unfinished gridding (in case of loop error)
		if pgrep -f "v.vol.rst" > /dev/null; then
			pkill -f v.vol.rst
			sleep 0.5
		fi
		# 3D wind field gridding	
		start_gridding_time=$(date +%s)
		grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec bash -c "
			g.region vect=computing_area_buf t=${dem_max} b=${dem_min} res=400 res3=400 tbres=50 -a -p -3
			v.vol.rst input=wind cross_input=${dem} wcolumn=u_wind tension=30 smooth=0.01 zscale=${scale_xy_z} segmax=700 cross_output=u_wind_tmp elevation=u_wind_3D_tmp &
			pid1=\$!
			v.vol.rst input=wind cross_input=${dem} wcolumn=v_wind tension=30 smooth=0.01 zscale=${scale_xy_z} segmax=700 cross_output=v_wind_tmp elevation=v_wind_3D_tmp &
			pid2=\$!
			wait \"\$pid1\" \"\$pid2\"
			r.mapcalc expression=\"ws_tmp=if(sqrt(u_wind_tmp^2+v_wind_tmp^2)<0,0,sqrt(u_wind_tmp^2+v_wind_tmp^2))\" &
			pid1=\$!
			r.mapcalc expression=\"wd_tmp=atan(v_wind_tmp,u_wind_tmp)\" &
			pid2=\$!
			wait \"\$pid1\" \"\$pid2\"
			r.mapcalc expression=\"wd_inv_tmp=if(wd_tmp+180>360,wd_tmp+180-360,wd_tmp+180)\"
		"
			
		flock -x "${TRAMONE_folder}/.wind_GIS_layers_lock" grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec bash -c "
			#g.rename vector=wind_tmp,wind
			#v.db.connect map=wind table=wind --overwrite
			g.rename raster=u_wind_tmp,u_wind
			g.rename raster=v_wind_tmp,v_wind
			g.rename raster=ws_tmp,ws
			g.rename raster=wd_tmp,wd
			g.rename raster=wd_inv_tmp,wd_inv
			
			v.what.rast ${sampling_sites_map} raster=ws column=ws
			v.what.rast ${sampling_sites_map} raster=wd column=wd
		"

		wind_to_log="$(grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec v.db.select ${sampling_sites_map} column=site,ws,wd)"
		out=""
		skip_header=1
		while IFS='|' read -r site ws wd; do
			if (( skip_header )); then
				skip_header=0
				continue
			fi			
			# skip empty lines
			[[ -z "$site" ]] && continue
			out+="$(date '+%Y-%m-%d %H:%M:%S')|${site}|WIND|${ws}|${wd}|OK"$'\n'
		done <<< "$wind_to_log"
		out="${out%$'\n'}"
		# write ws and wd to log
		exec 3>"${TRAMONE_folder}/.log_lock"
			flock -x 3
			printf '%s\n' "$out" >> "${TRAMONE_folder}/log.txt"
			flock -u 3
		exec 3>&-

		end_gridding_time=$(date +%s)
		echo "************************************************************************"
		echo "Wind 3D gridding completed in" $(( end_gridding_time - start_gridding_time )) "seconds."
		echo "************************************************************************"
		echo $(( end_gridding_time - start_gridding_time )) > "${TRAMONE_folder}/gridding_time.txt"
		
		wind_head_prev=$wind_head_for_grid
		wind_tail_prev=$wind_tail_for_grid
	fi
}	



map_maker() {
	echo "*********************"
	echo "Mapmaker started."
	echo "*********************"
	export GRASS_RENDER_IMMEDIATE=cairo
	export GRASS_RENDER_WIDTH=800
	export GRASS_RENDER_HEIGHT=800
	export GRASS_RENDER_TRANSPARENT=TRUE
	export GRASS_RENDER_FILE_READ=TRUE
	export GRASS_RENDER_LINE_WIDTH=1
	export WIND_OVERRIDE=mapmaker_region_${region}
	export GRASS_RENDER_FILE="${TRAMONE_folder}/${png_name}"
	flock -s "${TRAMONE_folder}/.wind_GIS_layers_lock" grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec bash -c '
		base_map="$1"
		region="$2"
		d.erase bgcolor=white
		d.rast "$base_map"
		d.vect checkpoints color="240:133:144" fill_color=none width=2 where="checkpoint LIKE '\''%S%'\''"
		rows=$(g.region -p | awk -F": *" "/^rows:/{print \$2}")
		cols=$(g.region -p | awk -F": *" "/^cols:/{print \$2}")
		nsres=$(g.region -p | awk -F": *" "/^nsres:/{print \$2}")
		ewres=$(g.region -p | awk -F": *" "/^ewres:/{print \$2}")
		ns=$(echo "$rows * $nsres" | bc)
		ew=$(echo "$cols * $ewres" | bc)
		if [ "$(echo "$ns > $ew" | bc)" -eq 1 ]; then
		arrow_res=$(echo "$ns / 50" | bc)
		else
		arrow_res=$(echo "$ew / 50" | bc)
		fi
		g.region res="$arrow_res" -a
		d.rast.arrow map=wd_inv type=compass magnitude_map=ws scale=1 skip=1 grid=none color="aqua"
		d.vect "site_${region}A_buf" color="20:56:127" fill_color="none" width=2
		d.vect "site_${region}B_buf" color="231:51:49" fill_color="none" width=2
		d.vect traj size=3 color=none fill_color="20:56:127" icon=basic/circle where="site='\''${region}A'\''"
		d.vect traj size=3 color=none fill_color="231:51:49" icon=basic/circle where="site='\''${region}B'\''"
		d.vect wind size=8 width=2 color="none" fill_color="aqua" icon=basic/circle
		v.label map=wind labels=ws column="ws" fontsize=7 color="aqua" reference=lower,left xoffset=4 yoffset=0 border="white" width=8
		d.labels ws
		v.label map=wind labels=wd column="wd" fontsize=7 color="aqua" reference=center,left xoffset=3 yoffset=5 border="white" width=8
		d.labels wd
		v.label map=wind labels=ws column="ws" fontsize=7 color="aqua" reference=lower,left xoffset=4 yoffset=0 border="white" width=8
		d.labels ws
		v.label map=wind labels=wd column="wd" fontsize=7 color="aqua" reference=center,left xoffset=3 yoffset=5 border="white" width=8
		d.labels wd
		' _ "$base_map" "$region"

}













#########################################################################
# init start

if [ -f "${TRAMONE_folder}/sampling_region_sites" ]; then
	rm "${TRAMONE_folder}/sampling_region_sites"
fi

pinctrl set 4 op
pinctrl set 4 dl

export GRASS_OVERWRITE=1

sudo timedatectl set-timezone UTC

if [[ ! -d "$TRAMONE_folder" ]]; then
	mkdir ${TRAMONE_folder}
fi

if [ -f "${TRAMONE_folder}/grassdata/cr-jtsk/TRAMONE/.gislock" ]; then
	echo ".gislock found. Removing."
	rm "${TRAMONE_folder}/grassdata/cr-jtsk/TRAMONE/.gislock"
fi

if [ ! -f "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}/sqlite/TRAMONE.db" ]; then
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec db.createdb database=${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}/sqlite/TRAMONE.db driver=sqlite
fi
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec db.connect database=${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}/sqlite/TRAMONE.db driver=sqlite

sampling_site_names=`grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select ${sampling_sites_map} column=site|tail -n +2|sort|uniq`
sampling_regions=`echo $sampling_site_names | tr ' ' '\n' | cut -c1 | sort -u | tr '\n' ' '`
sampling_sites=$(echo "$sampling_site_names" | cut -c2 | sort -u)

grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select ${sampling_sites_map} columns="site,x,y,repre_range" sep="," | tail -n +2 > ${TRAMONE_folder}/sampling_sites.txt
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec g.region rast=${base_map}
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.in.region computing_area
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.buffer computing_area out=computing_area_buf distance=10000
if grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec g.list type=raster pattern=MASK | grep -qx MASK; then
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.mask -r
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.mask vect=computing_area_buf
else
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.mask vect=computing_area_buf
fi
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.univar ${dem}
dem_min=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.univar ${dem} | grep minimum:|awk '{print $2}')	
dem_max=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.univar ${dem} | grep maximum:|awk '{print $2}')	
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.in.region computing_area_buf
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}  --exec r.mapcalc expression="u_wind=0" &
grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec r.mapcalc expression="v_wind=0" &
wait

echo $sampling_site_names

# buffer for sampling sites and the creation of the sampler operation time file
for site in $sampling_site_names
do
	if [ ! -d "${TRAMONE_folder}/MQTT/TRAMONE/${site}" ]; then
		mkdir -p "${TRAMONE_folder}/MQTT/TRAMONE/${site}"
	fi
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.extract ${sampling_sites_map} out=site_${site} where="site=='${site}'" 
	repre_range=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select -c map=${sampling_sites_map} column=repre_range where="site=='${site}'")
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.buffer site_${site} out=site_${site}_buf distance=$repre_range
	if [ ! -f "${TRAMONE_folder}/${site}_0" ]; then
		echo "0.0" > ${TRAMONE_folder}/${site}_0
	fi
	if [ ! -f "${TRAMONE_folder}/${site}_1" ]; then
		echo "0.0" > ${TRAMONE_folder}/${site}_1
	fi
done

checkpoints=`grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select checkpoints column=checkpoint -c | tr '\n' ' ' | sed 's/.$//'`
checkpoint_columns=`grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select checkpoints column=checkpoint -c | sed 's/^/@/' | sed 's/@/pass_/g' | tr '[:space:] ' '@' | sed 's/@/ integer,/g' | sed 's/,$//'`
checkpoints_number=`grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select checkpoints column=checkpoint -c | wc -l`
checkpoints_init_val=`yes "0," | head -n ${checkpoints_number} | tr -d '\n' | sed 's/.$//'`

if [ ! -d "${TRAMONE_folder}/shp" ]; then
	mkdir ${TRAMONE_folder}/shp
fi
if [ ! -d "${TRAMONE_folder}/img" ]; then
	mkdir ${TRAMONE_folder}/img
fi
if [ ! -d "${TRAMONE_folder}/wind" ]; then
	mkdir ${TRAMONE_folder}/wind
fi
if [ ! -f "${TRAMONE_folder}/time_prev_hour.txt" ]; then
	time_prev_hour=`TZ=UTC date +"%Y%m%d%H"`
	echo $time_prev_hour > ${TRAMONE_folder}/time_prev_hour.txt
fi

time_shp=0

if [ -f "${TRAMONE_folder}/traj.txt" ]; then
	sed -i '/,,,/d' ${TRAMONE_folder}/traj.txt
fi

lxterminal -T "TRAMONE MAIN (logs)" -e journalctl --user-unit=tramone_main.service -f --no-pager &
lxterminal -T "TRAMONE NETWORKING (logs)" -e journalctl --user-unit=tramone_networking.service -f --no-pager &

wind_gridding_pid=""
sleep 1

#waiting for display variables
	export DISPLAY=${DISPLAY:-:0}
	export XAUTHORITY=${XAUTHORITY:-/home/pi/.Xauthority}
	until xdpyinfo >/dev/null 2>&1; do
	  sleep 0.2
	done

SAMPLING_REGIONS=$(printf '%s\n' $sampling_regions | paste -sd, -)
SAMPLING_SITES=$(printf '%s\n' $sampling_sites | paste -sd, -)
systemctl --user set-environment SAMPLING_REGIONS="$SAMPLING_REGIONS" SAMPLING_SITES="$SAMPLING_SITES"
systemd-notify --ready

rm /home/pi/TRAMONE/networking_on

########################################################################
# main loop start
while :
do

	date_UTC=`date -u +"%Y-%m-%d %H:%M:%S"`

	#test the function of the networking
	while [ ! -f "/home/pi/TRAMONE/networking_on" ]
	do
	    echo "Waiting for networking..."
	    sleep 3
	done
	time_now=$(date +%s)
	last_networking_time=$(stat -c %Y "/home/pi/TRAMONE/networking_on")
	time_diff=$((time_now - last_networking_time))
	if [ "$time_diff" -gt 180 ]; then
	    echo "Network hangs !!!"
		systemctl --user restart tramone_networking.service
	fi
	
	#if wind field gridding finished, launch new gridding
	if [[ -z "$wind_gridding_pid" ]] || ! kill -0 "$wind_gridding_pid" 2>/dev/null; then
		wind_gridding &
		wind_gridding_pid=$!
	fi
	
#recent time and loop time increment for traj
	time_prev_sec=`cat ${TRAMONE_folder}/time_prev_sec.txt`
	time_now_sec=`TZ=UTC date +"%s"`
	diff_time_sec=`echo "$time_now_sec - $time_prev_sec"|bc`
	echo $time_now_sec > ${TRAMONE_folder}/time_prev_sec.txt
	echo "time_now_sec: " $time_now_sec
	echo "time_prev_sec: " $time_prev_sec
	echo "diff_time_sec: " $diff_time_sec
	
#add new trajectory point at each monitoring site buffer zone
	while read radek
	do
		IFS="," read -r pairsite x y repre_range <<< ${radek}
		repre_range=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select -c map=${sampling_sites_map} column=repre_range where="site=='${pairsite}'")
		echo "-----------------------------------"
		echo $pairsite"|"$x"|"$y"|"$repre_range
		echo "time_now_sec: " $time_now_sec
		pts_number=$(echo "-0.4 * $diff_time_sec + 15"|bc)
		pts_number=$(printf "%.0f\n" "$pts_number")
		if (( pts_number > 12 )); then
			pts_number=12
		elif (( pts_number < 1 )); then
			pts_number=1
		fi
		for ((i=1; i<=pts_number; i++)); do
			angle=$(echo "scale=6; 2 * 3.141593 * $RANDOM / 32767" | bc)
			distance=$(echo "scale=6; $RANDOM / 32767 * $repre_range" | bc)
			dx=$(echo "scale=6; $distance * c($angle)" | bc -l)
			dy=$(echo "scale=6; $distance * s($angle)" | bc -l)
			echo "distance   dx     dy"
			echo $distance   $dx   $dy
			x_perturb=`echo "$x + $dx"|bc`
			y_perturb=`echo "$y + $dy"|bc`
			echo "${pairsite},${x_perturb},${y_perturb},${time_now_sec},${x},${y},999,999,${checkpoints_init_val},'XXX'" >> ${TRAMONE_folder}/traj.txt
		done
	done < ${TRAMONE_folder}/sampling_sites.txt

#remove corrupted lines (with no coords)
	sed -i '/,,,/d' ${TRAMONE_folder}/traj.txt
	
#move all trajectory points according the wind and time increment
	flock -x "${TRAMONE_folder}/.wind_GIS_layers_lock" grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec bash -c '
		v.in.ascii input="'"${TRAMONE_folder}"'/traj.txt" out=traj x=2 y=3 sep="," columns="site varchar(3),x real,y real,time integer,x_puv real,y_puv real,u_wind_prev real,v_wind_prev real,'"${checkpoint_columns}"',check_pass varchar(25)"
		v.db.addcolumn traj column="u_wind real,v_wind real,x_new real,y_new real"
		v.what.rast traj raster=u_wind column=u_wind
		v.what.rast traj raster=v_wind column=v_wind
		echo 
		db.execute sql="UPDATE traj SET x_new=x-u_wind*'"${diff_time_sec}"'"
		db.execute sql="UPDATE traj SET y_new=y-v_wind*'"${diff_time_sec}"'"
		#filter out points outside region and older than max_traj_time (sec) and save trajectory points to the text file
		v.select ainput=traj binput=computing_area_buf operator=within output=traj_reg
		# export zpět do ASCII (jen platné trajektorie)
		v.db.select traj_reg columns="site,x_new,y_new,time,x,y,u_wind,v_wind,'"${checkpoint_columns}"',check_pass" where="'"${time_now_sec}"'-time<'"${max_traj_time}"'" separator="," | tail -n +2 > "'"${TRAMONE_folder}"'/traj.txt"
		#read trajectory points at updated (moved) coordinates
		'
#remove corrupted lines (with no coords)
	sed -i '/,,,/d' ${TRAMONE_folder}/traj.txt
	flock -x "${TRAMONE_folder}/.wind_GIS_layers_lock" grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec bash -c '
		v.in.ascii input="'"${TRAMONE_folder}"'/traj.txt" out=traj x=2 y=3 sep="," columns="site varchar(3),x real,y real,time integer,x_puv real,y_puv real,u_wind_prev real,v_wind_prev real,'"${checkpoint_columns}"',check_pass"
		'
	
	traj_npoints=$(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.info traj | grep  "Number of points" |  grep -oP 'Number of points:\s+\K\d+')
	echo "||||||||||||||||||||||||||"
	echo $traj_npoints
	echo "||||||||||||||||||||||||||"
	if (( traj_npoints < 1 )); then
		for region in $sampling_regions
		do	
			echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}A/request"
			echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}B/request"	
		done
		echo "TRAJECTORIES CORRUPTED!!! PROGRAM STOPPED!!!"
		while :
		do
			sleep 1
		done
	fi


#draw the maps (mapmaker function)
	pids=()
	for region in $sampling_regions; do
		png_name="tramone_${region}.png"
		base_map="bg_map_${region}"
		grass -f --text "${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset}" --exec g.region raster="${base_map}" -a save="mapmaker_region_${region}"
		map_maker &
		pids+=($!)
		if ! pgrep -fa "${TRAMONE_folder}/tramone_${region}.png"; then
			feh "${TRAMONE_folder}/tramone_${region}.png" &
		fi
	done
	wait "${pids[@]}"
	#hourly wind and map saving
	time_now_hour=`TZ=UTC date +"%Y%m%d%H"`
	time_prev_hour=`cat ${TRAMONE_folder}/time_prev_hour.txt`
	if [ "$time_now_hour" -gt "$time_prev_hour" ]; then
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec g.copy vect=traj,traj_export
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.addcolumn traj_export column="time2 varchar(19)"
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.update traj_export column=time2 query_column="datetime(time, 'unixepoch', 'localtime')" 
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.renamecolumn map=traj_export column=u_wind_prev,u_wind_p
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.renamecolumn map=traj_export column=v_wind_prev,v_wind_p
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.out.ogr -s -e traj_export out=${TRAMONE_folder}/shp/traj_${time_now_hour}.shp format=ESRI_Shapefile
		exec 4>"${TRAMONE_folder}/.wind_text_files_lock"
			flock -s 4
			cp ${TRAMONE_folder}/wind.csv ${TRAMONE_folder}/wind/wind_${time_now_hour}.csv 
			flock -u 4
		exec 4>&-
		for region in $sampling_regions
		do	
			png_name="tramone_${region}.png"
			cp "${TRAMONE_folder}/${png_name}" "${TRAMONE_folder}/img/${time_now_hour}_${png_name}"		
		done
		time_prev_hour=$time_now_hour
		echo $time_prev_hour > ${TRAMONE_folder}/time_prev_hour.txt
	fi

	
	
	
	
	#check if trajectory points are now passing through the checkpoints
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.update traj column=check_pass value="XXX"
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.what.vect map=traj column=check_pass query_map=checkpoints query_column=checkpoint

	#record the pass through individual checkpoints
	for checkpoint in ${checkpoints}
	do
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.update map=traj column=pass_${checkpoint} where="check_pass='${checkpoint}'" value=pass_${checkpoint}+1
	done



	

#check conditions and switch on/off samplers
	echo "****************************************************"	
	for region in $sampling_regions
	do	
		# if trajectory passes in direction site A -> source -> site B
		if [ $(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec db.select -c sql="SELECT * FROM traj WHERE site='${region}A' AND pass_${region}S>0 AND pass_${region}B>0" | wc -l) -gt 0 ]; then
			last_OK_A=$(< ${TRAMONE_folder}/log.txt | grep response | grep '|${region}A|' | grep 'STATE|10|OK' | tail -n 1 | cut -d'|' -f1 | date +%s)
			last_OK_B=$(< ${TRAMONE_folder}/log.txt | grep response | grep '|${region}B|' | grep 'STATE|10|OK' | tail -n 1 | cut -d'|' -f1 | date +%s)
			last_OK_A=${last_OK_A:-0}
			last_OK_B=${last_OK_B:-0}
			# if last OK state occured at least 1 day ago, retry the normal condition handling
			if (( (last_OK_A < $(date +%s) - 87600) )); then
				last_OK_A=$(date +%s)
			fi
			if (( last_OK_B < $(date +%s) - 87600 )); then
				last_OK_B=$(date +%s)
			fi
			# if the state of any of samplers in the sampling pair is not OK for more than 3 minutes, then stop both samplers
			if (( (last_OK_A < $(date +%s) - 180) || (last_OK_B < $(date +%s) - 180) )); then
				echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}A/request"
				echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}B/request"
				echo "###########################################################################"
				echo "###########################################################################"
				echo "###########################################################################"
				echo "ERROR during sampling in region ${region} => samplers stopped for 24hrs !!!"
				echo "###########################################################################"
				echo "###########################################################################"
				echo "###########################################################################"
			# otherwise (if the states of both samplers in the sampling pair are in line with requests) normal request handling
			else
				echo  "10" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}A/request"
				echo  "10" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}B/request"
				echo "Sampling ${region}A -> ${region}S -> ${region}B"
				echo $(date +%s) > "${TRAMONE_folder}/sampling_start_time_${region}"
			fi
		# if trajectory passes in direction site B -> source -> site A
		elif [ $(grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec db.select -c sql="SELECT * FROM traj WHERE site='${region}B' AND pass_${region}S>0 AND pass_${region}A>0" | wc -l) -gt 0 ]; then
			last_OK_A=$(< ${TRAMONE_folder}/log.txt | grep response | grep '|${region}A|' | grep 'STATE|01|OK' | tail -n 1 | cut -d'|' -f1 | date +%s)
			last_OK_B=$(< ${TRAMONE_folder}/log.txt | grep response | grep '|${region}B|' | grep 'STATE|01|OK' | tail -n 1 | cut -d'|' -f1 | date +%s)	
			last_OK_A=${last_OK_A:-0}
			last_OK_B=${last_OK_B:-0}
			# if last OK state occured at least 1 day ago, retry the normal condition handling
			if (( (last_OK_A < $(date +%s) - 87600) )); then
				last_OK_A=$(date +%s)
			fi
			if (( last_OK_B < $(date +%s) - 87600 )); then
				last_OK_B=$(date +%s)
			fi	
			# if the state of any of samplers in the sampling pair is not OK for more than 3 minutes, then stop both samplers
			if (( (last_OK_A < $(date +%s) - 180) || (last_OK_B < $(date +%s) - 180) )); then
				echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}A/request"
				echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}B/request"
				echo "###########################################################################"
				echo "###########################################################################"
				echo "###########################################################################"
				echo "ERROR during sampling in region ${region} => samplers stopped for 24hrs !!!"
				echo "###########################################################################"
				echo "###########################################################################"
				echo "###########################################################################"
			# otherwise (if the states of both samplers in the sampling pair are in line with requests) normal request handling
			else
				echo  "01" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}A/request"
				echo  "01" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}B/request"
				echo "Sampling ${region}B -> ${region}S -> ${region}A"
				echo $(date +%s) > "${TRAMONE_folder}/sampling_start_time_${region}"
			fi
		# if the trajectory do not pass all checkpoints in any direction 
		else
			if [ -f "${TRAMONE_folder}/sampling_start_time_${region}" ]; then
				sampling_start_time=$(<"${TRAMONE_folder}/sampling_start_time_${region}")
			else
				sampling_start_time=0
			fi
			# the condition to protect samplers (sample 1 min after last request before switching off)
			if (( sampling_start_time < $(date +%s) - 60 )); then
				echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}A/request"
				echo  "00" > "${TRAMONE_folder}/MQTT/TRAMONE/${region}B/request"
				echo "No sampling ${region}A <-> ${region}S <-> ${region}B"
			fi
		fi

		#reset the counter of the opposite checkpoint for the new evaluation in the next loop (otherwise the sampling would never stop)
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec db.execute sql="UPDATE traj SET pass_${region}B=0 WHERE site='${region}A'"
		grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec db.execute sql="UPDATE traj SET pass_${region}A=0 WHERE site='${region}B'"
		
	done
	echo "****************************************************"	

#export trajectory points with info on checkpoints passing to ascii text file
	grass -f --text ${TRAMONE_folder}/${grassdb}/${loc_jtsk}/${mapset} --exec v.db.select traj columns="site,x,y,time,x_puv,y_puv,u_wind_prev,v_wind_prev,${checkpoint_columns},check_pass" separator=","|tail -n +2 > ${TRAMONE_folder}/traj.txt

done
