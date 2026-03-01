import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from audio_upscaler.upscaler import AudioUpscaler

def test_upscaler_init_mock():
    with patch('audiosr.build_model') as mock_build:
        mock_build.return_value = MagicMock()
        upscaler = AudioUpscaler()
        assert upscaler.device in ['cuda', 'cpu']
        mock_build.assert_called_once()

def test_upscale_mock():
    with patch('audiosr.build_model'), \
         patch('audiosr.super_resolution') as mock_sr, \
         patch('soundfile.write') as mock_sf_write:

        # Mock numpy array
        mock_waveform = MagicMock()
        mock_waveform.shape = (1, 1000)
        mock_sr.return_value = mock_waveform

        upscaler = AudioUpscaler()

        # Create library/uploads if not exists
        os.makedirs('library/uploads', exist_ok=True)
        os.makedirs('library/processed', exist_ok=True)

        input_file = 'library/uploads/test_input.wav'
        with open(input_file, 'wb') as f:
            f.write(b'dummy audio content')

        try:
            output_path = upscaler.upscale(input_file)
            assert 'test_input_upscaled.wav' in output_path
            assert os.path.basename(output_path) == 'test_input_upscaled.wav'
            mock_sr.assert_called_once()
            mock_sf_write.assert_called_once()
        finally:
            # Cleanup
            if os.path.exists(input_file):
                os.remove(input_file)
