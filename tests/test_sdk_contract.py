"""Verify adapter property names against the installed SDK without opening devices."""
import pytest


def test_installed_sdk_property_contract():
    pytest.importorskip('libtiepie')
    from libtiepie.generator import Generator
    from libtiepie.oscilloscope import Oscilloscope
    from libtiepie.oscilloscopechannel import OscilloscopeChannel
    from libtiepie.oscilloscopetrigger import OscilloscopeTrigger
    required={Generator:'signal_type frequency_mode frequency frequency_max data_length_max amplitude offset mode burst_count output_enable is_running is_burst_active trigger_inputs trigger_outputs',
              Oscilloscope:'measure_modes measure_mode channels sample_rate record_length record_length_max pre_sample_ratio trigger trigger_inputs is_data_ready',
              OscilloscopeChannel:'enabled trigger is_differential coupling auto_ranging range has_safeground safeground_enabled',
              OscilloscopeTrigger:'timeout'}
    for cls,names in required.items():
        for name in names.split(): assert hasattr(cls,name),f'{cls.__name__}.{name}'
