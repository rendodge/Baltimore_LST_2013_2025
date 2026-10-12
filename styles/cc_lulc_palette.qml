<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis hasScaleBasedVisibilityFlag="0" maxScale="0" minScale="1e+08" autoRefreshMode="Disabled" autoRefreshTime="0" version="3.44.15-Solothurn" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal fetchMode="0" bandNumber="1" enabled="0" mode="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <elevation symbology="Line" zoffset="0" band="1" zscale="1" enabled="0" mode="RepresentsElevationSurface">
    <data-defined-properties>
      <Option type="Map">
        <Option type="QString" value="" name="name"/>
        <Option name="properties"/>
        <Option type="QString" value="collection" name="type"/>
      </Option>
    </data-defined-properties>
    <profileLineSymbol>
      <symbol type="line" is_animated="0" frame_rate="10" alpha="1" clip_to_extent="1" force_rhr="0" name="">
        <data_defined_properties>
          <Option type="Map">
            <Option type="QString" value="" name="name"/>
            <Option name="properties"/>
            <Option type="QString" value="collection" name="type"/>
          </Option>
        </data_defined_properties>
        <layer id="{53906591-da0a-4423-af33-4f49275dffc9}" locked="0" class="SimpleLine" enabled="1" pass="0">
          <Option type="Map">
            <Option type="QString" value="0" name="align_dash_pattern"/>
            <Option type="QString" value="square" name="capstyle"/>
            <Option type="QString" value="5;2" name="customdash"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="customdash_map_unit_scale"/>
            <Option type="QString" value="MM" name="customdash_unit"/>
            <Option type="QString" value="0" name="dash_pattern_offset"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="dash_pattern_offset_map_unit_scale"/>
            <Option type="QString" value="MM" name="dash_pattern_offset_unit"/>
            <Option type="QString" value="0" name="draw_inside_polygon"/>
            <Option type="QString" value="bevel" name="joinstyle"/>
            <Option type="QString" value="225,89,137,255,rgb:0.8823529,0.3490196,0.5372549,1" name="line_color"/>
            <Option type="QString" value="solid" name="line_style"/>
            <Option type="QString" value="0.6" name="line_width"/>
            <Option type="QString" value="MM" name="line_width_unit"/>
            <Option type="QString" value="0" name="offset"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
            <Option type="QString" value="MM" name="offset_unit"/>
            <Option type="QString" value="0" name="ring_filter"/>
            <Option type="QString" value="0" name="trim_distance_end"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="trim_distance_end_map_unit_scale"/>
            <Option type="QString" value="MM" name="trim_distance_end_unit"/>
            <Option type="QString" value="0" name="trim_distance_start"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="trim_distance_start_map_unit_scale"/>
            <Option type="QString" value="MM" name="trim_distance_start_unit"/>
            <Option type="QString" value="0" name="tweak_dash_pattern_on_corners"/>
            <Option type="QString" value="0" name="use_custom_dash"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="width_map_unit_scale"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option type="QString" value="" name="name"/>
              <Option name="properties"/>
              <Option type="QString" value="collection" name="type"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </profileLineSymbol>
    <profileFillSymbol>
      <symbol type="fill" is_animated="0" frame_rate="10" alpha="1" clip_to_extent="1" force_rhr="0" name="">
        <data_defined_properties>
          <Option type="Map">
            <Option type="QString" value="" name="name"/>
            <Option name="properties"/>
            <Option type="QString" value="collection" name="type"/>
          </Option>
        </data_defined_properties>
        <layer id="{bf618475-2a7c-4b8a-819d-68126048f933}" locked="0" class="SimpleFill" enabled="1" pass="0">
          <Option type="Map">
            <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
            <Option type="QString" value="225,89,137,255,rgb:0.8823529,0.3490196,0.5372549,1" name="color"/>
            <Option type="QString" value="bevel" name="joinstyle"/>
            <Option type="QString" value="0,0" name="offset"/>
            <Option type="QString" value="3x:0,0,0,0,0,0" name="offset_map_unit_scale"/>
            <Option type="QString" value="MM" name="offset_unit"/>
            <Option type="QString" value="35,35,35,255,rgb:0.1372549,0.1372549,0.1372549,1" name="outline_color"/>
            <Option type="QString" value="no" name="outline_style"/>
            <Option type="QString" value="0.26" name="outline_width"/>
            <Option type="QString" value="MM" name="outline_width_unit"/>
            <Option type="QString" value="solid" name="style"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option type="QString" value="" name="name"/>
              <Option name="properties"/>
              <Option type="QString" value="collection" name="type"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </profileFillSymbol>
  </elevation>
  <customproperties>
    <Option type="Map">
      <Option type="QString" value="Value" name="identify/format"/>
    </Option>
  </customproperties>
  <mapTip enabled="1"></mapTip>
  <pipe-data-defined-properties>
    <Option type="Map">
      <Option type="QString" value="" name="name"/>
      <Option name="properties"/>
      <Option type="QString" value="collection" name="type"/>
    </Option>
  </pipe-data-defined-properties>
  <pipe>
    <provider>
      <resampling maxOversampling="2" enabled="false" zoomedOutResamplingMethod="nearestNeighbour" zoomedInResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer type="paletted" opacity="1" alphaBand="-1" band="1" nodataColor="">
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <colorPalette>
        <paletteEntry color="#1f5fa8" value="10" label="10 Tidal Waters" alpha="255"/>
        <paletteEntry color="#2f78c4" value="11" label="11 Lakes and Reservoirs" alpha="255"/>
        <paletteEntry color="#4a8fd6" value="12" label="12 Riverine Ponds" alpha="255"/>
        <paletteEntry color="#6aa6e0" value="13" label="13 Terrene Ponds" alpha="255"/>
        <paletteEntry color="#3c84cf" value="14" label="14 Streams and Rivers" alpha="255"/>
        <paletteEntry color="#e8dcb5" value="15" label="15 Bare Shore" alpha="255"/>
        <paletteEntry color="#3d3d3d" value="20" label="20 Roads" alpha="255"/>
        <paletteEntry color="#c0392b" value="21" label="21 Structures" alpha="255"/>
        <paletteEntry color="#9a9a9a" value="22" label="22 Other Impervious" alpha="255"/>
        <paletteEntry color="#5b8c3a" value="23" label="23 Tree Canopy Over Roads" alpha="255"/>
        <paletteEntry color="#6e9a3c" value="24" label="24 Tree Canopy Over Structures" alpha="255"/>
        <paletteEntry color="#7fa84a" value="25" label="25 Tree Canopy Over Other Impervious" alpha="255"/>
        <paletteEntry color="#4f9a4a" value="26" label="26 Tree Canopy Over Turf Grass" alpha="255"/>
        <paletteEntry color="#b5dc7f" value="27" label="27 Turf Grass" alpha="255"/>
        <paletteEntry color="#d9c49a" value="28" label="28 Bare Developed" alpha="255"/>
        <paletteEntry color="#c9a27a" value="30" label="30 Extractive Barren" alpha="255"/>
        <paletteEntry color="#a8865f" value="31" label="31 Extractive Impervious" alpha="255"/>
        <paletteEntry color="#5c4b8a" value="32" label="32 Solar Field Panel Arrays" alpha="255"/>
        <paletteEntry color="#8a7cb0" value="33" label="33 Solar Field Barren" alpha="255"/>
        <paletteEntry color="#a79bc8" value="34" label="34 Solar Field Herbaceous" alpha="255"/>
        <paletteEntry color="#c2b8dd" value="35" label="35 Solar Field Shrubland" alpha="255"/>
        <paletteEntry color="#e3cfa3" value="36" label="36 Suspended Succession Barren" alpha="255"/>
        <paletteEntry color="#e6e08c" value="37" label="37 Suspended Succession Herbaceous" alpha="255"/>
        <paletteEntry color="#c9c46a" value="38" label="38 Suspended Succession Shrubland" alpha="255"/>
        <paletteEntry color="#1b5e20" value="40" label="40 Forest" alpha="255"/>
        <paletteEntry color="#2e7d32" value="41" label="41 Forested Other" alpha="255"/>
        <paletteEntry color="#d8c79a" value="42" label="42 Natural Succession Barren" alpha="255"/>
        <paletteEntry color="#d4e49a" value="43" label="43 Natural Succession Herbaceous" alpha="255"/>
        <paletteEntry color="#a3b85a" value="44" label="44 Natural Succession Shrubland" alpha="255"/>
        <paletteEntry color="#bfa57a" value="45" label="45 Harvested Forest Barren" alpha="255"/>
        <paletteEntry color="#c7cf8a" value="46" label="46 Harvested Forest Herbaceous" alpha="255"/>
        <paletteEntry color="#b9d7d2" value="50" label="50 Riverine Wetlands Barren" alpha="255"/>
        <paletteEntry color="#7fc4b8" value="51" label="51 Riverine Wetlands Herbaceous" alpha="255"/>
        <paletteEntry color="#5aaf9f" value="52" label="52 Riverine Wetlands Shrubland" alpha="255"/>
        <paletteEntry color="#3d9583" value="53" label="53 Riverine Wetlands Forested Other" alpha="255"/>
        <paletteEntry color="#2a7a6a" value="54" label="54 Riverine Wetlands Forest" alpha="255"/>
        <paletteEntry color="#8ab8ad" value="55" label="55 Riverine Wetlands Harvested Forest" alpha="255"/>
        <paletteEntry color="#c6dbe0" value="60" label="60 Terrene Wetlands Barren" alpha="255"/>
        <paletteEntry color="#93c9d6" value="61" label="61 Terrene Wetlands Herbaceous" alpha="255"/>
        <paletteEntry color="#6db3c4" value="62" label="62 Terrene Wetlands Shrubland" alpha="255"/>
        <paletteEntry color="#4e9aae" value="63" label="63 Terrene Wetlands Forested Other" alpha="255"/>
        <paletteEntry color="#357f94" value="64" label="64 Terrene Wetlands Forest" alpha="255"/>
        <paletteEntry color="#9cc2cc" value="65" label="65 Terrene Wetlands Harvested Forest" alpha="255"/>
        <paletteEntry color="#cfd8e8" value="70" label="70 Tidal Wetlands Barren" alpha="255"/>
        <paletteEntry color="#9fb6db" value="71" label="71 Tidal Wetlands Herbaceous" alpha="255"/>
        <paletteEntry color="#7b98c9" value="72" label="72 Tidal Wetlands Shrubland" alpha="255"/>
        <paletteEntry color="#5d7fb8" value="73" label="73 Tidal Wetlands Forested Other" alpha="255"/>
        <paletteEntry color="#46679f" value="74" label="74 Tidal Wetlands Forest" alpha="255"/>
        <paletteEntry color="#a9b9d6" value="75" label="75 Tidal Wetlands Harvested Forest" alpha="255"/>
        <paletteEntry color="#e0b77a" value="80" label="80 Cropland Barren" alpha="255"/>
        <paletteEntry color="#f0d38c" value="81" label="81 Cropland Herbaceous" alpha="255"/>
        <paletteEntry color="#d9a36b" value="82" label="82 Orchards and Vineyards Barren" alpha="255"/>
        <paletteEntry color="#e8c27f" value="83" label="83 Orchards and Vineyards Herbaceous" alpha="255"/>
        <paletteEntry color="#c99a5c" value="84" label="84 Orchards and Vineyards Shrubland" alpha="255"/>
        <paletteEntry color="#e6cf9a" value="85" label="85 Pasture and Hay Barren" alpha="255"/>
        <paletteEntry color="#f2e3a1" value="86" label="86 Pasture and Hay Herbaceous" alpha="255"/>
      </colorPalette>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation colorizeStrength="100" colorizeRed="255" colorizeBlue="128" invertColors="0" colorizeOn="0" saturation="0" colorizeGreen="128" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
