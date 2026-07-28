# Rscript
library(dplyr)
library(lubridate)
args=commandArgs(trailingOnly=T)
wind=args[1]
stanice=args[2]
TRAMONE_folder=args[3]
wind_AIM=args[4]
stanice_AIM=args[5]

#parse the wind file and select only valid lines (to solve possible download errors) 
lines=readLines(wind)
header=strsplit(lines[1]," +")[[1]]
num_cols=length(header)
split_lines=strsplit(lines," +")
valid_lines=lines[sapply(split_lines, length)==num_cols]
wind=read.table(text=paste(valid_lines, collapse="\n"),quote="",skip=0,dec=",",header=T,fill=T)
print(head(wind))
print(tail(wind))

#wind=read.table(wind,sep="",quote="",skip=0,dec=",",header=T, fill=T)
wind=wind[2:nrow(wind),]
wind[,7]=gsub(",","\\.",wind[,7])
colnames(wind)[colnames(wind)=="DPRUM"]="D"
colnames(wind)[colnames(wind)=="FPRUM"]="F"
wind[,c(2:4,6,7)]=as.numeric(unlist(wind[,c(2:4,6,7)]))
#wind=wind[which(!(wind$F==0&wind$D==0)),]
wind$HOUR=as.numeric(substr(wind$TIME,1,2))
wind$MINUTE=as.numeric(substr(wind$TIME,4,5))
#imported CLIDATA are in CET => import and conversion to UTC
wind$date=ISOdate(wind$YEAR,wind$MONTH,wind$DAY,wind$HOUR,wind$MINUTE,tz="Etc/GMT-1")
wind$date=with_tz(wind$date,tzone="UTC")

#filter only last from duplicite rows for each station
wind=wind %>% group_by(EG_GH_ID) %>% slice_tail(n=1) %>% ungroup()

maxdate=max(wind$date, na.rm=T)
wind=wind %>% filter(date>maxdate-minutes(15))
if (nrow(wind)<3) 
{
	print(max(wind$date))
	print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
	print("Isufficient number of stations with the wind record time <15 minutes ago!")  
	print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
}

#wind_time=max(wind$date)
wind$u_wind=-wind$F*sin((wind$D+180)*pi/180)
wind$v_wind=-wind$F*cos((wind$D+180)*pi/180)
stanice=read.table(stanice,sep=",",quote="",header=T, fill=T)
data=left_join(wind,stanice,by=c("EG_GH_ID"="Gh_id"))
data$Elevation=round(data$Elevation)
data=data[,c("EG_GH_ID","D","F","u_wind","v_wind","east","north","Elevation","date")]
data=data[!is.na(data$east) & !is.na(data$north),]
if (nrow(data)>=3) {
	write.csv(data,paste0(TRAMONE_folder,"/wind.csv"),na="",row.names=F,quote=F)
} else {
	print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
	print("Isufficient number of rows in the wind file!")  
	print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
}
wind=data




if (file.exists(wind_AIM) & file.exists(stanice_AIM)) {
	age_secs <- as.numeric(difftime(Sys.time(), file.info(wind_AIM)$mtime, units = "secs"))
	if (age_secs <= 15 * 60) {
		lines <- readLines(wind_AIM)
		header=strsplit(lines[1],"\\t+")[[1]]
		num_cols=length(header)
		split_lines=strsplit(lines,"\\t+")
		valid_lines=lines[sapply(split_lines, length)==length(header)]
		wind_AIM=read.table(text=paste(valid_lines,collapse="\n"), sep="\t", quote="", skip=0, dec=",", header=T, fill=T)
		names(wind_AIM)[1] <- "date"
		#AIM wind time is the start of the 10-minute interval => shift to the real time:
		wind_AIM$date <- as.POSIXct(wind_AIM$date, format = "%d.%m.%y %H:%M", tz="UTC") + minutes(10)
		wind_AIM=wind_AIM[nrow(wind_AIM),]
		sites <- unique(sub("_(wd|ws)$", "", names(wind_AIM)[-1])) 
		out <- do.call(rbind, lapply(sites, function(site) {
		  data.frame(
		    date    = wind_AIM$date,
		    EG_GH_ID = site,
		    D      = wind_AIM[[paste0(site, "_wd")]],
		    F      = wind_AIM[[paste0(site, "_ws")]],
		    row.names = NULL
		  )
		}))
		out[,c(3,4)]=as.numeric(unlist(out[,c(3,4)]))
		out$F=round(out$F,1)
		out$D=round(out$D)
		out <- out[order(out$date, out$EG_GH_ID), ]
		wind_AIM <- out
		wind_AIM$u_wind=-wind_AIM$F*sin((wind_AIM$D+180)*pi/180)
		wind_AIM$v_wind=-wind_AIM$F*cos((wind_AIM$D+180)*pi/180)
		stanice_AIM=read.table(stanice_AIM,sep="",quote="",header=T, fill=T)
		data=left_join(wind_AIM,stanice_AIM,by=c("EG_GH_ID"="Gh_id"))
		data$Elevation=round(data$Elevation)
		data=data[,c("EG_GH_ID","D","F","u_wind","v_wind","east","north","Elevation","date")]
		data=data[!is.na(data$east) & !is.na(data$north),]
		if (nrow(data)>=3) {
			write.csv(data,paste0(TRAMONE_folder,"/wind_AIM.csv"),na="",row.names=F,quote=F)
		} else {
			print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
			print("Isufficient number of rows in the wind file!")  
			print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
		}
		wind_AIM=data
		wind=rbind(wind,wind_AIM)
		wind=wind[!is.na(wind$D) & !is.na(wind$F),]
		print(head(wind))
		print(tail(wind))
		if (nrow(wind)>=3) {
			write.csv(wind,paste0(TRAMONE_folder,"/wind.csv"),na="",row.names=F,quote=F)
		} else {
			print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
			print("Isufficient number of rows in the wind file!")  
			print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
		}		

		
	}
}
