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
        <layer id="{bdd9e132-5a6c-4374-b0d4-c913e88cf8ad}" locked="0" class="SimpleLine" enabled="1" pass="0">
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
            <Option type="QString" value="229,182,54,255,rgb:0.8980392,0.7137255,0.2117647,1" name="line_color"/>
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
        <layer id="{7413ff8c-7554-4dbd-bae3-c1274c63f471}" locked="0" class="SimpleFill" enabled="1" pass="0">
          <Option type="Map">
            <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
            <Option type="QString" value="229,182,54,255,rgb:0.8980392,0.7137255,0.2117647,1" name="color"/>
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
    <rasterrenderer type="singlebandpseudocolor" opacity="1" alphaBand="-1" band="1" classificationMin="30" nodataColor="" classificationMax="50">
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" labelPrecision="6" minimumValue="30" maximumValue="50" classificationMode="1" clip="0">
          <colorramp type="gradient" name="[source]">
            <Option type="Map">
              <Option type="QString" value="0,0,4,255,rgb:0,0,0.0156863,1" name="color1"/>
              <Option type="QString" value="252,255,164,255,rgb:0.9882353,1,0.6431373,1" name="color2"/>
              <Option type="QString" value="ccw" name="direction"/>
              <Option type="QString" value="0" name="discrete"/>
              <Option type="QString" value="gradient" name="rampType"/>
              <Option type="QString" value="rgb" name="spec"/>
              <Option type="QString" value="0.0196078;2,2,12,255,rgb:0.0078431,0.0078431,0.0470588,1;rgb;ccw:0.0392157;5,4,23,255,rgb:0.0196078,0.0156863,0.0901961,1;rgb;ccw:0.0588235;10,7,34,255,rgb:0.0392157,0.027451,0.1333333,1;rgb;ccw:0.0784314;16,9,45,255,rgb:0.0627451,0.0352941,0.1764706,1;rgb;ccw:0.0980392;22,11,57,255,rgb:0.0862745,0.0431373,0.2235294,1;rgb;ccw:0.117647;30,12,69,255,rgb:0.1176471,0.0470588,0.2705882,1;rgb;ccw:0.137255;38,12,81,255,rgb:0.1490196,0.0470588,0.3176471,1;rgb;ccw:0.156863;47,10,91,255,rgb:0.1843137,0.0392157,0.3568627,1;rgb;ccw:0.176471;56,9,98,255,rgb:0.2196078,0.0352941,0.3843137,1;rgb;ccw:0.196078;64,10,103,255,rgb:0.2509804,0.0392157,0.4039216,1;rgb;ccw:0.215686;73,11,106,255,rgb:0.2862745,0.0431373,0.4156863,1;rgb;ccw:0.235294;81,14,108,255,rgb:0.3176471,0.054902,0.4235294,1;rgb;ccw:0.254902;89,16,110,255,rgb:0.3490196,0.0627451,0.4313725,1;rgb;ccw:0.27451;97,19,110,255,rgb:0.3803922,0.0745098,0.4313725,1;rgb;ccw:0.294118;105,22,110,255,rgb:0.4117647,0.0862745,0.4313725,1;rgb;ccw:0.313725;113,25,110,255,rgb:0.4431373,0.0980392,0.4313725,1;rgb;ccw:0.333333;120,28,109,255,rgb:0.4705882,0.1098039,0.427451,1;rgb;ccw:0.352941;128,31,108,255,rgb:0.5019608,0.1215686,0.4235294,1;rgb;ccw:0.372549;136,34,106,255,rgb:0.5333333,0.1333333,0.4156863,1;rgb;ccw:0.392157;144,37,104,255,rgb:0.5647059,0.145098,0.4078431,1;rgb;ccw:0.411765;152,39,102,255,rgb:0.5960784,0.1529412,0.4,1;rgb;ccw:0.431373;160,42,99,255,rgb:0.627451,0.1647059,0.3882353,1;rgb;ccw:0.45098;168,46,95,255,rgb:0.6588235,0.1803922,0.372549,1;rgb;ccw:0.470588;176,49,91,255,rgb:0.6901961,0.1921569,0.3568627,1;rgb;ccw:0.490196;183,53,87,255,rgb:0.7176471,0.2078431,0.3411765,1;rgb;ccw:0.509804;191,57,82,255,rgb:0.7490196,0.2235294,0.3215686,1;rgb;ccw:0.529412;198,61,77,255,rgb:0.7764706,0.2392157,0.3019608,1;rgb;ccw:0.54902;204,66,72,255,rgb:0.8,0.2588235,0.2823529,1;rgb;ccw:0.568627;211,71,67,255,rgb:0.827451,0.2784314,0.2627451,1;rgb;ccw:0.588235;217,77,61,255,rgb:0.8509804,0.3019608,0.2392157,1;rgb;ccw:0.607843;223,83,55,255,rgb:0.8745098,0.3254902,0.2156863,1;rgb;ccw:0.627451;228,90,49,255,rgb:0.8941176,0.3529412,0.1921569,1;rgb;ccw:0.647059;233,97,43,255,rgb:0.9137255,0.3803922,0.1686275,1;rgb;ccw:0.666667;237,105,37,255,rgb:0.9294118,0.4117647,0.145098,1;rgb;ccw:0.686275;241,113,31,255,rgb:0.945098,0.4431373,0.1215686,1;rgb;ccw:0.705882;244,121,24,255,rgb:0.9568627,0.4745098,0.0941176,1;rgb;ccw:0.72549;247,130,18,255,rgb:0.9686275,0.5098039,0.0705882,1;rgb;ccw:0.745098;249,139,11,255,rgb:0.9764706,0.545098,0.0431373,1;rgb;ccw:0.764706;250,148,7,255,rgb:0.9803922,0.5803922,0.027451,1;rgb;ccw:0.784314;251,157,7,255,rgb:0.9843137,0.6156863,0.027451,1;rgb;ccw:0.803922;252,166,12,255,rgb:0.9882353,0.6509804,0.0470588,1;rgb;ccw:0.823529;252,176,20,255,rgb:0.9882353,0.6901961,0.0784314,1;rgb;ccw:0.843137;251,186,31,255,rgb:0.9843137,0.7294118,0.1215686,1;rgb;ccw:0.862745;250,196,42,255,rgb:0.9803922,0.7686275,0.1647059,1;rgb;ccw:0.882353;248,205,55,255,rgb:0.972549,0.8039216,0.2156863,1;rgb;ccw:0.901961;246,215,70,255,rgb:0.9647059,0.8431373,0.2745098,1;rgb;ccw:0.921569;244,225,86,255,rgb:0.9568627,0.8823529,0.3372549,1;rgb;ccw:0.941176;242,234,105,255,rgb:0.9490196,0.9176471,0.4117647,1;rgb;ccw:0.960784;242,242,125,255,rgb:0.9490196,0.9490196,0.4901961,1;rgb;ccw:0.980392;245,249,146,255,rgb:0.9607843,0.9764706,0.572549,1;rgb;ccw" name="stops"/>
            </Option>
          </colorramp>
          <item color="#000004" value="30" label="30" alpha="255"/>
          <item color="#02020c" value="30.392156" label="30.4" alpha="255"/>
          <item color="#050417" value="30.784314" label="30.8" alpha="255"/>
          <item color="#0a0722" value="31.176470000000002" label="31.2" alpha="255"/>
          <item color="#10092d" value="31.568628" label="31.6" alpha="255"/>
          <item color="#160b39" value="31.960784" label="32" alpha="255"/>
          <item color="#1e0c45" value="32.352940000000004" label="32.4" alpha="255"/>
          <item color="#260c51" value="32.7451" label="32.7" alpha="255"/>
          <item color="#2f0a5b" value="33.13726" label="33.1" alpha="255"/>
          <item color="#380962" value="33.52942" label="33.5" alpha="255"/>
          <item color="#400a67" value="33.92156" label="33.9" alpha="255"/>
          <item color="#490b6a" value="34.31372" label="34.3" alpha="255"/>
          <item color="#510e6c" value="34.70588" label="34.7" alpha="255"/>
          <item color="#59106e" value="35.09804" label="35.1" alpha="255"/>
          <item color="#61136e" value="35.4902" label="35.5" alpha="255"/>
          <item color="#69166e" value="35.88236" label="35.9" alpha="255"/>
          <item color="#71196e" value="36.2745" label="36.3" alpha="255"/>
          <item color="#781c6d" value="36.66666" label="36.7" alpha="255"/>
          <item color="#801f6c" value="37.05882" label="37.1" alpha="255"/>
          <item color="#88226a" value="37.45098" label="37.5" alpha="255"/>
          <item color="#902568" value="37.84314" label="37.8" alpha="255"/>
          <item color="#982766" value="38.2353" label="38.2" alpha="255"/>
          <item color="#a02a63" value="38.62746" label="38.6" alpha="255"/>
          <item color="#a82e5f" value="39.0196" label="39" alpha="255"/>
          <item color="#b0315b" value="39.41176" label="39.4" alpha="255"/>
          <item color="#b73557" value="39.80392" label="39.8" alpha="255"/>
          <item color="#bf3952" value="40.19608" label="40.2" alpha="255"/>
          <item color="#c63d4d" value="40.58824" label="40.6" alpha="255"/>
          <item color="#cc4248" value="40.9804" label="41" alpha="255"/>
          <item color="#d34743" value="41.37254" label="41.4" alpha="255"/>
          <item color="#d94d3d" value="41.7647" label="41.8" alpha="255"/>
          <item color="#df5337" value="42.15686" label="42.2" alpha="255"/>
          <item color="#e45a31" value="42.54902" label="42.5" alpha="255"/>
          <item color="#e9612b" value="42.94118" label="42.9" alpha="255"/>
          <item color="#ed6925" value="43.33334" label="43.3" alpha="255"/>
          <item color="#f1711f" value="43.7255" label="43.7" alpha="255"/>
          <item color="#f47918" value="44.11764" label="44.1" alpha="255"/>
          <item color="#f78212" value="44.5098" label="44.5" alpha="255"/>
          <item color="#f98b0b" value="44.90196" label="44.9" alpha="255"/>
          <item color="#fa9407" value="45.29412" label="45.3" alpha="255"/>
          <item color="#fb9d07" value="45.68628" label="45.7" alpha="255"/>
          <item color="#fca60c" value="46.07844" label="46.1" alpha="255"/>
          <item color="#fcb014" value="46.47058" label="46.5" alpha="255"/>
          <item color="#fbba1f" value="46.86274" label="46.9" alpha="255"/>
          <item color="#fac42a" value="47.2549" label="47.3" alpha="255"/>
          <item color="#f8cd37" value="47.647059999999996" label="47.6" alpha="255"/>
          <item color="#f6d746" value="48.03922" label="48" alpha="255"/>
          <item color="#f4e156" value="48.431380000000004" label="48.4" alpha="255"/>
          <item color="#f2ea69" value="48.82352" label="48.8" alpha="255"/>
          <item color="#f2f27d" value="49.21568" label="49.2" alpha="255"/>
          <item color="#f5f992" value="49.607839999999996" label="49.6" alpha="255"/>
          <item color="#fcffa4" value="50" label="50" alpha="255"/>
          <rampLegendSettings minimumLabel="" orientation="2" direction="0" suffix="" maximumLabel="" useContinuousLegend="1" prefix="">
            <numericFormat id="basic">
              <Option type="Map">
                <Option type="invalid" name="decimal_separator"/>
                <Option type="int" value="6" name="decimals"/>
                <Option type="int" value="0" name="rounding_type"/>
                <Option type="bool" value="false" name="show_plus"/>
                <Option type="bool" value="true" name="show_thousand_separator"/>
                <Option type="bool" value="false" name="show_trailing_zeros"/>
                <Option type="invalid" name="thousand_separator"/>
              </Option>
            </numericFormat>
          </rampLegendSettings>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation colorizeStrength="100" colorizeRed="255" colorizeBlue="128" invertColors="0" colorizeOn="0" saturation="0" colorizeGreen="128" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
