#!/usr/bin/env python
# coding: utf-8

### FEMS Real-time Fire Danger for Southwest Montana Zone FDOP
#### Written by: W. Matt Jolly
#### Version: 0.4 alpha  (Workings graphs and all hourly->daily->SIG summaries)
#### Date:  12 May 2026
###### Modified from: FEMS Technical Handout


import requests, json, bisect
import numpy as np
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import geopandas as gpd
import datetime as datetime
import contextily as cx
from scipy import stats
from pathlib import Path
import logging
from FEMSHelpers import *
import Constants



if __name__ == "__main__":
    
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    
    # Create a path object
    path = Path("Tables/")
    path.mkdir(parents=True, exist_ok=True)
    
    path = Path("Figures/")
    path.mkdir(parents=True, exist_ok=True)

    
    # Colors for plotting from Red Yel Blue Colorbrewer palette
    col1 = '#d53e4f'  # Red
    col2 = '#fc8d59'
    col3 = '#fee08b'
    col4 = '#ffffbf'  # Yellow
    col5 = '#e6f598'
    col6 = '#99d594'
    col7 = '#3288bd'  # Blue
        
    url_fuelmodel = 'https://fems.fs2c.usda.gov/fuelmodel/apis/graphql' 
    url_climatology = 'https://fems.fs2c.usda.gov/api/climatology/graphql' 
    
    # Setup a synchronous transport to pass to the client
    transport = RequestsHTTPTransport(url=url_climatology,headers={"X-API-Key": Constants.API_KEY})
    
    # Create a GraphQL client
    client = Client(transport=transport)
    
    ## Get the FEMS station list and format it as a GeoPandas DataFrame
    gdfStations = MakeFEMSWXStationDataframe(client)
    
    myStations = gdfStations[gdfStations.StationID.isin([241508,241513,241507,241302,241206,241403,241206,242911,242910,242902,101019,242915,242912,242907,242905,242914])]
    myStationsVoronoi = myStations.voronoi_polygons()
    
    ### Define the historical data files for each FDRA
    lolo_west_fdra_hist_file = 'Data/lwfdr_histfd_Y.csv'
    lolo_east_fdra_hist_file = 'Data/lefdr_histfd_Y.csv'
    cskt_east_fdra_hist_file = 'Data/cskte_histfd_Y.csv'
    cskt_west_fdra_hist_file = 'Data/csktw_histfd_Y.csv'
    brf_high_fdra_hist_file = 'Data/brh_histfd_Y.csv'
    brf_low_fdra_hist_file = 'Data/brl_histfd_Y_Z.csv'
    
    
    ### Define the station lists for each FDRA
    lefdr_sta_id = str("241507,241508,241513")
    lwfdr_sta_id = str("241507,241302,241206")
    csktefdr_sta_id = str("241403")
    csktwfdr_sta_id = str("241403,241206")
    bhfdr_sta_id = str("242911,242910,242902,101019")
    blfdr_sta_id = str("242915,242912,242907,242905,242914")
    
    
    ### Build the historical data for each FDRA based on the selected fuel model
    df_hist_nfdrs_lwfdra    =  BuildSingleNFDRSHist(lolo_west_fdra_hist_file, myFuelModel = "Y")
    df_hist_nfdrs_lwfdra.reset_index(inplace=True)
    df_hist_nfdrs_lefdra    =  BuildSingleNFDRSHist(lolo_east_fdra_hist_file, myFuelModel = "Y")
    df_hist_nfdrs_lefdra.reset_index(inplace=True)
    df_hist_nfdrs_csktefdra =  BuildSingleNFDRSHist(cskt_east_fdra_hist_file, myFuelModel = "Y")
    df_hist_nfdrs_csktefdra.reset_index(inplace=True)
    df_hist_nfdrs_csktwfdra =  BuildSingleNFDRSHist(cskt_west_fdra_hist_file, myFuelModel = "Y")
    df_hist_nfdrs_csktwfdra.reset_index(inplace=True)
    df_hist_nfdrs_blfdra    =  BuildSingleNFDRSHist(brf_low_fdra_hist_file, myFuelModel = "Z")
    df_hist_nfdrs_blfdra.reset_index(inplace=True)
    df_hist_nfdrs_bhfdra    =  BuildSingleNFDRSHist(brf_high_fdra_hist_file, myFuelModel = "Y")
    df_hist_nfdrs_bhfdra.reset_index(inplace=True)
    
    logger.info('Built historical fire danger dataframes')
    ## Define all percentile thresholds for this Zone
    
    # ERC percentiles in the SW Zone 
    lefdra_erc_percs=[20,30,43,49]
    lwfdra_erc_percs=[14,30,44,51]
    csktefdra_erc_percs = [14,27,36,42]
    csktwfdra_erc_percs = [18,30,41,48]
    blfdra_erc_percs = [40,77,94,105]
    bhfdra_erc_percs = [15,33,45,52]
    
    # BI percentiles in the SW Zone 
    lefdra_bi_percs=[13,27]
    lwfdra_bi_percs=[14,28]
    csktefdra_bi_percs = [25,33]
    csktwfdra_bi_percs = [18,28]
    blfdra_bi_percs = [71,82] #[50,90]
    bhfdra_bi_percs = [20,40]
    
    # Create the Dispatch Response Level matrix
    # Note: These tables show be flipped vertically from the way they are displayed in the FDOP
    DRL_Matrix = np.array([
        ['L', 'L', 'L','M','M'],
       ['L', 'L', 'M','M','H'],
       ['L', 'L', 'M','H','H+'] 
        
    ])
     
    
    ## Summarize historical hourly data to daily 
    # Summarize hourly to daily
    df_hist_nfdrs_daily_lefdra = SummarizeDaily(df_hist_nfdrs_lefdra)
    df_hist_nfdrs_daily_lwfdra = SummarizeDaily(df_hist_nfdrs_lwfdra)
    df_hist_nfdrs_daily_csktefdra = SummarizeDaily(df_hist_nfdrs_csktefdra)
    df_hist_nfdrs_daily_csktwfdra = SummarizeDaily(df_hist_nfdrs_csktwfdra)
    df_hist_nfdrs_daily_blfdra = SummarizeDaily(df_hist_nfdrs_blfdra)
    df_hist_nfdrs_daily_bhfdra = SummarizeDaily(df_hist_nfdrs_bhfdra)
    
    # Filter for the FDOP analysis period
    df_hist_nfdrs_daily_lefdra = FilterDates(df_hist_nfdrs_daily_lefdra,"2005-01-01","2025-12-31")
    df_hist_nfdrs_daily_lwfdra = FilterDates(df_hist_nfdrs_daily_lwfdra,"2005-01-01","2025-12-31")
    df_hist_nfdrs_daily_csktefdra = FilterDates(df_hist_nfdrs_daily_csktefdra,"2005-01-01","2025-12-31")
    df_hist_nfdrs_daily_csktwfdra = FilterDates(df_hist_nfdrs_daily_csktwfdra,"2005-01-01","2025-12-31")
    df_hist_nfdrs_daily_blfdra = FilterDates(df_hist_nfdrs_daily_blfdra,"2005-01-01","2025-12-31")
    df_hist_nfdrs_daily_bhfdra = FilterDates(df_hist_nfdrs_daily_bhfdra,"2005-01-01","2025-12-31")
    
    
    ## Calculate the historical percentiles and SFDI and store the SFDI breakpoint tables
    df_hist_nfdrs_daily_lefdra, lefdra_sfdi_breaks = CalcHistPercs(df_hist_nfdrs_daily_lefdra)
    df_hist_nfdrs_daily_lwfdra, lwfdra_sfdi_breaks = CalcHistPercs(df_hist_nfdrs_daily_lwfdra)
    df_hist_nfdrs_daily_csktefdra, csktefdra_sfdi_breaks = CalcHistPercs(df_hist_nfdrs_daily_csktefdra)
    df_hist_nfdrs_daily_csktwfdra, csktwfdra_sfdi_breaks = CalcHistPercs(df_hist_nfdrs_daily_csktwfdra)
    df_hist_nfdrs_daily_blfdra, blfdra_sfdi_breaks = CalcHistPercs(df_hist_nfdrs_daily_blfdra)
    df_hist_nfdrs_daily_bhfdra, bhfdra_sfdi_breaks = CalcHistPercs(df_hist_nfdrs_daily_bhfdra)
    logger.info('Calculated historical percentiles and SFDI breakpoint table')
    
    sfdi_breaks = {'lefdra':lefdra_sfdi_breaks.values,'lwfdra':lwfdra_sfdi_breaks.values,'cskte':csktefdra_sfdi_breaks.values,'csktw':csktwfdra_sfdi_breaks.values,'blfdra':blfdra_sfdi_breaks.values,'bhfdra':bhfdra_sfdi_breaks.values}
    
    
    # Provide a GraphQL query
    query = gql(""" query NFDRSObs ($stationIds: String!,$FuelModels: String!,$StartDate: Date!,$EndDate:Date!) { 
    nfdrsObs(startDateRange: $StartDate endDateRange: $EndDate, stationIds: $stationIds, fuelModels: $FuelModels, per_page: 1000000, page: 0 ) { 
    data { station_name
      station_id
      wrcc_id
      latitude
      longitude
      elevation
      observation_time
      nfdr_date
      nfdr_time
      nfdr_type
      fuel_model
      fuel_model_version
      kbdi
      one_hr_tl_fuel_moisture
      ten_hr_tl_fuel_moisture
      hun_hr_tl_fuel_moisture
      thou_hr_tl_fuel_moisture
      ignition_component
      spread_component
      energy_release_component
      burning_index
      herbaceous_lfi_fuel_moisture
      woody_lfi_fuel_moisture
      gsi
      observation_type
    }}} """ 
    )
    
   
    # Create strings of yesterday, today and tomorrow dates for plotting and display
    yesterdayStr = (datetime.now() + timedelta(days=-1)).strftime("%Y-%m-%d")
    todayStr = (datetime.now() + timedelta(days=0)).strftime("%Y-%m-%d")
    tomorrowStr = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    
    ## Grab the real-time and forecast weather data for each FDRA
    df_lefdr = MakeFEMSNFDRSDataframe(GetRTFEMSData(lefdr_sta_id,client,query))
    df_lwfdr = MakeFEMSNFDRSDataframe(GetRTFEMSData(lwfdr_sta_id,client,query))
    logger.info('Got RT data for Lolo')
    df_csktefdr = MakeFEMSNFDRSDataframe(GetRTFEMSData(csktefdr_sta_id,client,query))
    df_csktwfdr = MakeFEMSNFDRSDataframe(GetRTFEMSData(csktwfdr_sta_id,client,query))
    logger.info('Got RT data for CSKT')
    df_blfdr = MakeFEMSNFDRSDataframe(GetRTFEMSData(blfdr_sta_id,client,query,FuelModel="Z"))
    df_bhfdr = MakeFEMSNFDRSDataframe(GetRTFEMSData(bhfdr_sta_id,client,query))
    logger.info('Got RT data for Bitterroot')
    
    
    
    
    lefdr_daily_max = SummarizeDailyRT(df_lefdr) #.groupby(df_lefdr.DateTime.dt.date).max()
    lwfdr_daily_max = SummarizeDailyRT(df_lwfdr)
    csktefdr_daily_max = SummarizeDailyRT(df_csktefdr)
    csktwfdr_daily_max = SummarizeDailyRT(df_csktwfdr)
    blfdr_daily_max = SummarizeDailyRT(df_blfdr)
    bhfdr_daily_max = SummarizeDailyRT(df_bhfdr)
    
    # Create a list of the historical and real-time data frames. Process assumes that they are paired.
    df_hists = ['df_hist_nfdrs_daily_lefdra','df_hist_nfdrs_daily_lwfdra','df_hist_nfdrs_daily_csktefdra','df_hist_nfdrs_daily_csktwfdra','df_hist_nfdrs_daily_blfdra','df_hist_nfdrs_daily_bhfdra']
    df_rt = ['lefdr_daily_max','lwfdr_daily_max','csktefdr_daily_max','csktwfdr_daily_max','blfdr_daily_max','bhfdr_daily_max']
    
    # Calculate the ERC, BI and SFDI percentiles
    for index, value in enumerate(df_hists):
        globals()[df_rt[index]]['ERCDailyMaxPerc'] = globals()[df_rt[index]].ERC.apply(lambda x: stats.percentileofscore(globals()[df_hists[index]].ERCDailyMax,x))
        globals()[df_rt[index]]['BIDailyMaxPerc'] = globals()[df_rt[index]].BI.apply(lambda x: stats.percentileofscore(globals()[df_hists[index]].BIDailyMax,x))
        globals()[df_rt[index]]['SFDIDailyMaxPerc'] = globals()[df_rt[index]].ERCDailyMaxPerc/100 * globals()[df_rt[index]].BIDailyMaxPerc/100
    
    
    # Assign Fuel Models for each of the FDRAs
    lefdr_daily_max['FuelModel'] = "Y"
    lwfdr_daily_max['FuelModel'] = "Y"
    csktefdr_daily_max['FuelModel'] = "Y"
    csktwfdr_daily_max['FuelModel'] = "Y"
    blfdr_daily_max['FuelModel'] = "Z"
    bhfdr_daily_max['FuelModel'] = "Y"
    
    
    # Calcualte the SFDI class using the sfdi_breaks lookup table
    lefdr_daily_max['SFDI'] = lefdr_daily_max.apply(lambda row: LookupClass(row['SFDIDailyMaxPerc'],sfdi_breaks['lefdra']), axis=1)
    lwfdr_daily_max['SFDI'] = lwfdr_daily_max.apply(lambda row: LookupClass(row['SFDIDailyMaxPerc'],sfdi_breaks['lwfdra']), axis=1)
    csktefdr_daily_max['SFDI'] = csktefdr_daily_max.apply(lambda row: LookupClass(row['SFDIDailyMaxPerc'],sfdi_breaks['cskte']), axis=1)
    csktwfdr_daily_max['SFDI'] = csktwfdr_daily_max.apply(lambda row: LookupClass(row['SFDIDailyMaxPerc'],sfdi_breaks['csktw']), axis=1)
    blfdr_daily_max['SFDI'] = blfdr_daily_max.apply(lambda row: LookupClass(row['SFDIDailyMaxPerc'],sfdi_breaks['blfdra']), axis=1)
    bhfdr_daily_max['SFDI'] = bhfdr_daily_max.apply(lambda row: LookupClass(row['SFDIDailyMaxPerc'],sfdi_breaks['bhfdra']), axis=1)
    
    # Calculate the BI class from BI and the BI perc table
    lefdr_daily_max['BIClass'] = lefdr_daily_max.apply(lambda row: LookupClass(row['BI'],lefdra_bi_percs), axis=1)
    lwfdr_daily_max['BIClass'] = lwfdr_daily_max.apply(lambda row: LookupClass(row['BI'],lwfdra_bi_percs), axis=1)
    csktefdr_daily_max['BIClass'] = csktefdr_daily_max.apply(lambda row: LookupClass(row['BI'],csktefdra_bi_percs), axis=1)
    csktwfdr_daily_max['BIClass'] =csktwfdr_daily_max.apply(lambda row: LookupClass(row['BI'],csktwfdra_bi_percs), axis=1)
    blfdr_daily_max['BIClass'] = blfdr_daily_max .apply(lambda row: LookupClass(row['BI'],blfdra_bi_percs), axis=1)
    bhfdr_daily_max ['BIClass'] = bhfdr_daily_max .apply(lambda row: LookupClass(row['BI'],bhfdra_bi_percs), axis=1)
    
    # Calculate the ERC class from ERC and the ERC perc table
    lefdr_daily_max['ERCClass'] = lefdr_daily_max.apply(lambda row: LookupClass(row['ERC'],lefdra_erc_percs), axis=1)
    lwfdr_daily_max['ERCClass'] = lwfdr_daily_max.apply(lambda row: LookupClass(row['ERC'],lwfdra_erc_percs), axis=1)
    csktefdr_daily_max['ERCClass'] = csktefdr_daily_max.apply(lambda row: LookupClass(row['ERC'],csktefdra_erc_percs), axis=1)
    csktwfdr_daily_max['ERCClass'] =csktwfdr_daily_max.apply(lambda row: LookupClass(row['ERC'],csktwfdra_erc_percs), axis=1)
    blfdr_daily_max['ERCClass'] = blfdr_daily_max .apply(lambda row: LookupClass(row['ERC'],blfdra_erc_percs), axis=1)
    bhfdr_daily_max ['ERCClass'] = bhfdr_daily_max .apply(lambda row: LookupClass(row['ERC'],bhfdra_erc_percs), axis=1)
    
    # Calculate the Dispatch Reponse Level from the BI and ERC classes
    lefdr_daily_max['DRLClass'] = lefdr_daily_max.apply(lambda row: LookupDRLClass(int(row['ERCClass']),int(row['BIClass']),DRL_Matrix), axis=1)
    lwfdr_daily_max['DRLClass'] = lwfdr_daily_max.apply(lambda row: LookupDRLClass(int(row['ERCClass']),int(row['BIClass']),DRL_Matrix), axis=1)
    csktefdr_daily_max['DRLClass'] = csktefdr_daily_max.apply(lambda row: LookupDRLClass(int(row['ERCClass']),int(row['BIClass']),DRL_Matrix), axis=1)
    csktwfdr_daily_max['DRLClass'] = csktwfdr_daily_max.apply(lambda row: LookupDRLClass(int(row['ERCClass']),int(row['BIClass']),DRL_Matrix), axis=1)
    blfdr_daily_max['DRLClass'] = blfdr_daily_max.apply(lambda row: LookupDRLClass(int(row['ERCClass']),int(row['BIClass']),DRL_Matrix), axis=1)
    bhfdr_daily_max['DRLClass'] = bhfdr_daily_max.apply(lambda row: LookupDRLClass(int(row['ERCClass']),int(row['BIClass']),DRL_Matrix), axis=1)
    
    
    lefdr_daily_max.reset_index(inplace=True)
    lwfdr_daily_max.reset_index(inplace=True)
    csktefdr_daily_max.reset_index(inplace=True)
    csktwfdr_daily_max.reset_index(inplace=True)
    blfdr_daily_max.reset_index(inplace=True)
    bhfdr_daily_max.reset_index(inplace=True)
    
    
    lefdr_daily_max['FDRA'] = "Lolo East"
    lwfdr_daily_max['FDRA'] = "Lolo West"
    csktwfdr_daily_max['FDRA'] = "CSKT West"
    csktefdr_daily_max['FDRA'] = "CSKT East"
    bhfdr_daily_max['FDRA'] = "Bitterroot High"
    blfdr_daily_max['FDRA'] = "Bitterroot Low"
    
    
    daily_max = pd.concat([lefdr_daily_max,lwfdr_daily_max,csktwfdr_daily_max,csktefdr_daily_max,blfdr_daily_max,bhfdr_daily_max])
    daily_max.reset_index(inplace=True)
    
    daily_max['DateTime'] = pd.to_datetime(daily_max['DateTime'])
    daily_max = daily_max[daily_max.DateTime >= yesterdayStr]
    daily_max['DateTimeStr'] = daily_max['DateTime'].dt.strftime("%Y-%b-%d")
    
    
    # Make the Observation Table
    daily_max_today_table = daily_max[daily_max.DateTime.dt.strftime("%Y-%m-%d") == todayStr][['FDRA','ObsType','FuelModel','DateTimeStr','ERCDailyMaxPerc','BIDailyMaxPerc','SFDIDailyMaxPerc','SFDI','BIClass','ERCClass','DRLClass','ERC','BI']]
    daily_max_today_table['BItext'] = daily_max_today_table.apply(lambda row: BIClassToText(row['BIClass']), axis=1)
    daily_max_today_table['ERCtext'] = daily_max_today_table.apply(lambda row: ERCClassToText(row['ERCClass']), axis=1)
    daily_max_today_table['SFDItext'] = daily_max_today_table.apply(lambda row: SFDIClassToText(row['SFDI']), axis=1)
    daily_max_today_table = daily_max_today_table.drop(columns=['SFDIDailyMaxPerc','SFDI','BIClass','ERCClass'])[['FDRA','ObsType','FuelModel','DateTimeStr','ERC','ERCDailyMaxPerc','BI','BIDailyMaxPerc','ERCtext','BItext','DRLClass','SFDItext']].round(1)
    daily_max_today_table = daily_max_today_table.sort_values(by='ObsType')
    daily_max_today_table = daily_max_today_table.rename(columns={"DateTimeStr":"Date",
                                                                  "SFDItext":"SFDI",
                                                                  "ERCtext":"ERC Class",
                                                                  "BItext":"BI Class",
                                                                  "DRLClass":"Dispatch RL" , 
                                                                  "BIDailyMaxPerc":"BI Percentile",
                                                                  "ERCDailyMaxPerc":"ERC Percentile"})
    # If there are both O's and F's in the daily max data
    if len(daily_max_today_table.ObsType.unique()) == 2:
        daily_max_today_table_all = daily_max_today_table
        daily_max_today_table_obs = daily_max_today_table_all[daily_max_today_table_all.ObsType == "O"]
        daily_max_today_table_fcst = daily_max_today_table_all[daily_max_today_table_all.ObsType == "F"]
        daily_max_today_table_fcst.to_csv('Tables/fire_danger_table_today_forecast.csv', index=False)
        daily_max_today_table_obs.to_csv('Tables/fire_danger_table_today_obs.csv', index=False)
    else: # Otherwise, it'll just be F
        daily_max_today_table.to_csv('Tables/fire_danger_table_today_forecast.csv', index=False)
        daily_max_today_table.to_csv('Tables/fire_danger_table_today_obs.csv', index=False)
        
    
    
    
    
    
    
    # Make the Forecast Table
    daily_max_tomorrow_table = daily_max[daily_max.DateTime.dt.strftime("%Y-%m-%d") == tomorrowStr][['FDRA','ObsType','FuelModel','DateTimeStr','ERCDailyMaxPerc','BIDailyMaxPerc','SFDIDailyMaxPerc','SFDI','BIClass','ERCClass','DRLClass','ERC','BI']]
    daily_max_tomorrow_table['BItext'] = daily_max_tomorrow_table.apply(lambda row: BIClassToText(row['BIClass']), axis=1)
    daily_max_tomorrow_table['ERCtext'] = daily_max_tomorrow_table.apply(lambda row: ERCClassToText(row['ERCClass']), axis=1)
    daily_max_tomorrow_table['SFDItext'] = daily_max_tomorrow_table.apply(lambda row: SFDIClassToText(row['SFDI']), axis=1)
    daily_max_tomorrow_table=daily_max_tomorrow_table.drop(columns=['SFDIDailyMaxPerc','SFDI','BIClass','ERCClass'])[['FDRA','ObsType','FuelModel','DateTimeStr','ERC','ERCDailyMaxPerc','BI','BIDailyMaxPerc','ERCtext','BItext','DRLClass','SFDItext']].round(1)
    daily_max_tomorrow_table = daily_max_tomorrow_table.rename(columns={"DateTimeStr":"Date",
                                                                        "SFDItext":"SFDI",
                                                                        "ERCtext":"ERC Class",
                                                                        "BItext":"BI Class",
                                                                        "DRLClass":"Dispatch RL" , 
                                                                        "BIDailyMaxPerc":"BI Percentile",
                                                                        "ERCDailyMaxPerc":"ERC Percentile"})
    
    daily_max_tomorrow_table.to_csv('Tables/fire_danger_table_tomorrow.csv', index=False)
    
       
    
    units = []
    # Lolo East and West
    units.append({'rt_df':lefdr_daily_max,'hist_df':df_hist_nfdrs_daily_lefdra,'sta_list':lefdr_sta_id,'title':"Lolo East FDRA",'oFileBasePath': "Figures/LoloEastFDRA_",'Percs':{'ERC':lefdra_erc_percs},'FuelModel':"Y"})
    units.append({'rt_df':lwfdr_daily_max,'hist_df':df_hist_nfdrs_daily_lwfdra,'sta_list':lwfdr_sta_id,'title':"Lolo West FDRA",'oFileBasePath': "Figures/LoloWestFDRA_",'Percs':{'ERC':lwfdra_erc_percs},'FuelModel':"Y"})
    
    # CSKT East and West
    units.append({'rt_df':csktefdr_daily_max,'hist_df':df_hist_nfdrs_daily_csktefdra,'sta_list':csktefdr_sta_id,'title':"CSKT East FDRA",'oFileBasePath': "Figures/CSKTEastFDRA_",'Percs':{'ERC':csktefdra_erc_percs},'FuelModel':"Y"})
    units.append({'rt_df':csktwfdr_daily_max,'hist_df':df_hist_nfdrs_daily_csktwfdra,'sta_list':csktwfdr_sta_id,'title':"CSKT West FDRA",'oFileBasePath': "Figures/CSKTWestFDRA_",'Percs':{'ERC':csktwfdra_erc_percs},'FuelModel':"Y"})
    
    # Bitterroot High and Low
    units.append({'rt_df':blfdr_daily_max,'hist_df':df_hist_nfdrs_daily_blfdra,'sta_list':blfdr_sta_id,'title':"Bitterroot Low FDRA",'oFileBasePath': "Figures/BRFLowFDRA_",'Percs':{'ERC':blfdra_erc_percs},'FuelModel':"Z"})
    units.append({'rt_df':bhfdr_daily_max,'hist_df':df_hist_nfdrs_daily_bhfdra,'sta_list':bhfdr_sta_id,'title':"Bitterroot High FDRA",'oFileBasePath': "Figures/BRFHighFDRA_",'Percs':{'ERC':bhfdra_erc_percs},'FuelModel':"Y"})
    
        
    # Variables to plot
    variables = ['ERC','BI','MC1000','MC100']
    
    
    
    IterateFigures(units,variables,2026,todayStr)
    
