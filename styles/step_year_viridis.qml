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
        <layer id="{d5900f85-fa0a-488c-bbd2-9f74e1daee82}" locked="0" class="SimpleLine" enabled="1" pass="0">
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
            <Option type="QString" value="125,139,143,255,rgb:0.4901961,0.545098,0.5607843,1" name="line_color"/>
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
        <layer id="{e5a050b9-afa3-4605-bf21-0b01fa3f2bfd}" locked="0" class="SimpleFill" enabled="1" pass="0">
          <Option type="Map">
            <Option type="QString" value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale"/>
            <Option type="QString" value="125,139,143,255,rgb:0.4901961,0.545098,0.5607843,1" name="color"/>
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
    <rasterrenderer type="singlebandpseudocolor" opacity="1" alphaBand="-1" band="1" classificationMin="2015" nodataColor="" classificationMax="2023">
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader colorRampType="DISCRETE" labelPrecision="6" minimumValue="2015" maximumValue="2023" classificationMode="1" clip="0">
          <colorramp type="gradient" name="[source]">
            <Option type="Map">
              <Option type="QString" value="68,1,84,255,rgb:0.2666667,0.0039216,0.3294118,1" name="color1"/>
              <Option type="QString" value="253,231,37,255,rgb:0.9921569,0.9058824,0.145098,1" name="color2"/>
              <Option type="QString" value="ccw" name="direction"/>
              <Option type="QString" value="0" name="discrete"/>
              <Option type="QString" value="gradient" name="rampType"/>
              <Option type="QString" value="rgb" name="spec"/>
              <Option type="QString" value="0.0196078;70,8,92,255,rgb:0.2745098,0.0313725,0.3607843,1;rgb;ccw:0.0392157;71,16,99,255,rgb:0.2784314,0.0627451,0.3882353,1;rgb;ccw:0.0588235;72,23,105,255,rgb:0.2823529,0.0901961,0.4117647,1;rgb;ccw:0.0784314;72,29,111,255,rgb:0.2823529,0.1137255,0.4352941,1;rgb;ccw:0.0980392;72,36,117,255,rgb:0.2823529,0.1411765,0.4588235,1;rgb;ccw:0.117647;71,42,122,255,rgb:0.2784314,0.1647059,0.4784314,1;rgb;ccw:0.137255;70,48,126,255,rgb:0.2745098,0.1882353,0.4941176,1;rgb;ccw:0.156863;69,55,129,255,rgb:0.2705882,0.2156863,0.5058824,1;rgb;ccw:0.176471;67,61,132,255,rgb:0.2627451,0.2392157,0.5176471,1;rgb;ccw:0.196078;65,66,135,255,rgb:0.254902,0.2588235,0.5294118,1;rgb;ccw:0.215686;63,72,137,255,rgb:0.2470588,0.2823529,0.5372549,1;rgb;ccw:0.235294;61,78,138,255,rgb:0.2392157,0.3058824,0.5411765,1;rgb;ccw:0.254902;58,83,139,255,rgb:0.227451,0.3254902,0.545098,1;rgb;ccw:0.27451;56,89,140,255,rgb:0.2196078,0.3490196,0.5490196,1;rgb;ccw:0.294118;53,94,141,255,rgb:0.2078431,0.3686275,0.5529412,1;rgb;ccw:0.313725;51,99,141,255,rgb:0.2,0.3882353,0.5529412,1;rgb;ccw:0.333333;49,104,142,255,rgb:0.1921569,0.4078431,0.5568627,1;rgb;ccw:0.352941;46,109,142,255,rgb:0.1803922,0.427451,0.5568627,1;rgb;ccw:0.372549;44,113,142,255,rgb:0.172549,0.4431373,0.5568627,1;rgb;ccw:0.392157;42,118,142,255,rgb:0.1647059,0.4627451,0.5568627,1;rgb;ccw:0.411765;41,123,142,255,rgb:0.1607843,0.4823529,0.5568627,1;rgb;ccw:0.431373;39,128,142,255,rgb:0.1529412,0.5019608,0.5568627,1;rgb;ccw:0.45098;37,132,142,255,rgb:0.145098,0.5176471,0.5568627,1;rgb;ccw:0.470588;35,137,142,255,rgb:0.1372549,0.5372549,0.5568627,1;rgb;ccw:0.490196;33,142,141,255,rgb:0.1294118,0.5568627,0.5529412,1;rgb;ccw:0.509804;32,146,140,255,rgb:0.1254902,0.572549,0.5490196,1;rgb;ccw:0.529412;31,151,139,255,rgb:0.1215686,0.5921569,0.545098,1;rgb;ccw:0.54902;30,156,137,255,rgb:0.1176471,0.6117647,0.5372549,1;rgb;ccw:0.568627;31,161,136,255,rgb:0.1215686,0.6313725,0.5333333,1;rgb;ccw:0.588235;33,165,133,255,rgb:0.1294118,0.6470588,0.5215686,1;rgb;ccw:0.607843;36,170,131,255,rgb:0.1411765,0.6666667,0.5137255,1;rgb;ccw:0.627451;40,174,128,255,rgb:0.1568627,0.6823529,0.5019608,1;rgb;ccw:0.647059;46,179,124,255,rgb:0.1803922,0.7019608,0.4862745,1;rgb;ccw:0.666667;53,183,121,255,rgb:0.2078431,0.7176471,0.4745098,1;rgb;ccw:0.686275;61,188,116,255,rgb:0.2392157,0.7372549,0.454902,1;rgb;ccw:0.705882;70,192,111,255,rgb:0.2745098,0.7529412,0.4352941,1;rgb;ccw:0.72549;80,196,106,255,rgb:0.3137255,0.7686275,0.4156863,1;rgb;ccw:0.745098;90,200,100,255,rgb:0.3529412,0.7843137,0.3921569,1;rgb;ccw:0.764706;101,203,94,255,rgb:0.3960784,0.7960784,0.3686275,1;rgb;ccw:0.784314;112,207,87,255,rgb:0.4392157,0.8117647,0.3411765,1;rgb;ccw:0.803922;124,210,80,255,rgb:0.4862745,0.8235294,0.3137255,1;rgb;ccw:0.823529;137,213,72,255,rgb:0.5372549,0.8352941,0.2823529,1;rgb;ccw:0.843137;149,216,64,255,rgb:0.5843137,0.8470588,0.2509804,1;rgb;ccw:0.862745;162,218,55,255,rgb:0.6352941,0.854902,0.2156863,1;rgb;ccw:0.882353;176,221,47,255,rgb:0.6901961,0.8666667,0.1843137,1;rgb;ccw:0.901961;189,223,38,255,rgb:0.7411765,0.8745098,0.1490196,1;rgb;ccw:0.921569;202,225,31,255,rgb:0.7921569,0.8823529,0.1215686,1;rgb;ccw:0.941176;216,226,25,255,rgb:0.8470588,0.8862745,0.0980392,1;rgb;ccw:0.960784;229,228,25,255,rgb:0.8980392,0.8941176,0.0980392,1;rgb;ccw:0.980392;241,229,29,255,rgb:0.945098,0.8980392,0.1137255,1;rgb;ccw" name="stops"/>
            </Option>
          </colorramp>
          <item color="#440154" value="2015.1538458153846" label="2015.2" alpha="255"/>
          <item color="#46085c" value="2015.3076924153845" label="2015.3" alpha="255"/>
          <item color="#471063" value="2015.4615382307693" label="2015.5" alpha="255"/>
          <item color="#481769" value="2015.6153848307692" label="2015.6" alpha="255"/>
          <item color="#481d6f" value="2015.7692306461538" label="2015.8" alpha="255"/>
          <item color="#482475" value="2015.9230764615384" label="2015.9" alpha="255"/>
          <item color="#472a7a" value="2016.076923846154" label="2016.1" alpha="255"/>
          <item color="#46307e" value="2016.2307712307693" label="2016.2" alpha="255"/>
          <item color="#453781" value="2016.3846186153846" label="2016.4" alpha="255"/>
          <item color="#433d84" value="2016.5384581538462" label="2016.5" alpha="255"/>
          <item color="#414287" value="2016.6923055384616" label="2016.7" alpha="255"/>
          <item color="#3f4889" value="2016.846152923077" label="2016.8" alpha="255"/>
          <item color="#3d4e8a" value="2017.0000003076923" label="2017" alpha="255"/>
          <item color="#3a538b" value="2017.1538476923076" label="2017.2" alpha="255"/>
          <item color="#38598c" value="2017.307695076923" label="2017.3" alpha="255"/>
          <item color="#355e8d" value="2017.4615346153846" label="2017.5" alpha="255"/>
          <item color="#33638d" value="2017.615382" label="2017.6" alpha="255"/>
          <item color="#31688e" value="2017.7692293846153" label="2017.8" alpha="255"/>
          <item color="#2e6d8e" value="2017.9230767692309" label="2017.9" alpha="255"/>
          <item color="#2c718e" value="2018.0769241538462" label="2018.1" alpha="255"/>
          <item color="#2a768e" value="2018.2307715384616" label="2018.2" alpha="255"/>
          <item color="#297b8e" value="2018.384618923077" label="2018.4" alpha="255"/>
          <item color="#27808e" value="2018.5384584615385" label="2018.5" alpha="255"/>
          <item color="#25848e" value="2018.6923058461539" label="2018.7" alpha="255"/>
          <item color="#23898e" value="2018.8461532307692" label="2018.8" alpha="255"/>
          <item color="#218e8d" value="2019.0000006153846" label="2019" alpha="255"/>
          <item color="#20928c" value="2019.153848" label="2019.2" alpha="255"/>
          <item color="#1f978b" value="2019.3076953846153" label="2019.3" alpha="255"/>
          <item color="#1e9c89" value="2019.461534923077" label="2019.5" alpha="255"/>
          <item color="#1fa188" value="2019.6153823076922" label="2019.6" alpha="255"/>
          <item color="#21a585" value="2019.7692296923076" label="2019.8" alpha="255"/>
          <item color="#24aa83" value="2019.9230770769232" label="2019.9" alpha="255"/>
          <item color="#28ae80" value="2020.0769244615385" label="2020.1" alpha="255"/>
          <item color="#2eb37c" value="2020.2307718461539" label="2020.2" alpha="255"/>
          <item color="#35b779" value="2020.3846192307692" label="2020.4" alpha="255"/>
          <item color="#3dbc74" value="2020.5384587692308" label="2020.5" alpha="255"/>
          <item color="#46c06f" value="2020.6923061538462" label="2020.7" alpha="255"/>
          <item color="#50c46a" value="2020.8461535384615" label="2020.8" alpha="255"/>
          <item color="#5ac864" value="2021.0000009230769" label="2021" alpha="255"/>
          <item color="#65cb5e" value="2021.1538483076922" label="2021.2" alpha="255"/>
          <item color="#70cf57" value="2021.3076956923078" label="2021.3" alpha="255"/>
          <item color="#7cd250" value="2021.4615352307692" label="2021.5" alpha="255"/>
          <item color="#89d548" value="2021.6153826153845" label="2021.6" alpha="255"/>
          <item color="#95d840" value="2021.76923" label="2021.8" alpha="255"/>
          <item color="#a2da37" value="2021.9230773846155" label="2021.9" alpha="255"/>
          <item color="#b0dd2f" value="2022.0769247692308" label="2022.1" alpha="255"/>
          <item color="#bddf26" value="2022.2307721538461" label="2022.2" alpha="255"/>
          <item color="#cae11f" value="2022.3846116923078" label="2022.4" alpha="255"/>
          <item color="#d8e219" value="2022.5384590769231" label="2022.5" alpha="255"/>
          <item color="#e5e419" value="2022.6923064615385" label="2022.7" alpha="255"/>
          <item color="#f1e51d" value="2022.8461538461538" label="2022.8" alpha="255"/>
          <item color="#fde725" value="inf" label="inf" alpha="255"/>
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
