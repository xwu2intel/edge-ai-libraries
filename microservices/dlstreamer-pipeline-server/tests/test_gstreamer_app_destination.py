#
# Apache v2 license
# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.server.gstreamer_app_destination import GvaSample, GStreamerAppDestination
from src.server.gstreamer_pipeline import GStreamerPipeline


class TestGvaSample:
    """Tests for the lazy GvaSample class."""

    def test_sample_attribute_accessible(self):
        mock_sample = MagicMock()
        gva = GvaSample(mock_sample)
        assert gva.sample is mock_sample

    def test_video_frame_lazily_created(self, mocker):
        mock_sample = MagicMock()
        mock_video_frame = MagicMock()
        mock_vf_cls = mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=mock_video_frame,
        )
        gva = GvaSample(mock_sample)
        # VideoFrame should NOT be created on construction
        mock_vf_cls.assert_not_called()
        # Accessing video_frame should trigger construction
        result = gva.video_frame
        mock_vf_cls.assert_called_once_with(
            mock_sample.get_buffer(),
            caps=mock_sample.get_caps(),
        )
        assert result is mock_video_frame

    def test_video_frame_created_only_once(self, mocker):
        mock_sample = MagicMock()
        mock_vf_cls = mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=MagicMock(),
        )
        gva = GvaSample(mock_sample)
        _ = gva.video_frame
        _ = gva.video_frame
        # Should only be constructed once despite multiple accesses
        assert mock_vf_cls.call_count == 1

    def test_video_frame_none_on_exception(self, mocker):
        mock_sample = MagicMock()
        mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            side_effect=Exception("VideoFrame construction failed"),
        )
        gva = GvaSample(mock_sample)
        assert gva.video_frame is None

    def test_explicit_video_frame_not_recreated(self, mocker):
        mock_sample = MagicMock()
        mock_video_frame = MagicMock()
        mock_vf_cls = mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
        )
        gva = GvaSample(mock_sample, video_frame=mock_video_frame)
        result = gva.video_frame
        # VideoFrame class should not be called when video_frame is provided
        mock_vf_cls.assert_not_called()
        assert result is mock_video_frame

    def test_explicit_none_video_frame_not_recreated(self, mocker):
        mock_sample = MagicMock()
        mock_vf_cls = mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
        )
        # Explicitly passing None means "video_frame is None, don't lazily create"
        gva = GvaSample(mock_sample, video_frame=None)
        result = gva.video_frame
        mock_vf_cls.assert_not_called()
        assert result is None

    def test_truthy_check(self, mocker):
        mock_sample = MagicMock()
        mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=MagicMock(),
        )
        gva = GvaSample(mock_sample)
        # if gva.video_frame: should work
        assert bool(gva.video_frame) is True


class TestGStreamerAppDestination:
    """Tests for GStreamerAppDestination._create_output_item."""

    @pytest.fixture
    def mock_pipeline(self):
        pipeline = MagicMock(spec=GStreamerPipeline)
        return pipeline

    @pytest.fixture
    def dest(self, mock_pipeline):
        request = {
            'destination': {
                'metadata': {
                    'output': MagicMock(),
                    'mode': 'frames',
                }
            }
        }
        return GStreamerAppDestination(request, mock_pipeline)

    def test_frames_mode_returns_gva_sample_without_eager_video_frame(self, dest, mocker):
        mock_sample = MagicMock()
        mock_vf_cls = mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
        )
        result = dest._create_output_item(mock_sample)
        # VideoFrame should NOT be constructed eagerly in FRAMES mode
        mock_vf_cls.assert_not_called()
        assert isinstance(result, GvaSample)
        assert result.sample is mock_sample

    def test_frames_mode_video_frame_available_lazily(self, dest, mocker):
        mock_sample = MagicMock()
        mock_video_frame = MagicMock()
        mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=mock_video_frame,
        )
        result = dest._create_output_item(mock_sample)
        # Accessing video_frame now triggers lazy construction
        vf = result.video_frame
        assert vf is mock_video_frame

    def _make_dest(self, mock_pipeline, mode):
        request = {
            'destination': {
                'metadata': {
                    'output': MagicMock(),
                    'mode': mode,
                }
            }
        }
        return GStreamerAppDestination(request, mock_pipeline)

    def test_regions_mode_constructs_video_frame_eagerly(self, mock_pipeline, mocker):
        mock_video_frame = MagicMock()
        mock_video_frame.regions.return_value = ['region1']
        mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=mock_video_frame,
        )
        dest = self._make_dest(mock_pipeline, 'regions')
        result = dest._create_output_item(MagicMock())
        assert result == ['region1']

    def test_tensors_mode_constructs_video_frame_eagerly(self, mock_pipeline, mocker):
        mock_video_frame = MagicMock()
        mock_video_frame.tensors.return_value = ['tensor1']
        mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=mock_video_frame,
        )
        dest = self._make_dest(mock_pipeline, 'tensors')
        result = dest._create_output_item(MagicMock())
        assert result == ['tensor1']

    def test_messages_mode_constructs_video_frame_eagerly(self, mock_pipeline, mocker):
        mock_video_frame = MagicMock()
        mock_video_frame.messages.return_value = ['msg1']
        mocker.patch(
            'src.server.gstreamer_app_destination.VideoFrame',
            return_value=mock_video_frame,
        )
        dest = self._make_dest(mock_pipeline, 'messages')
        result = dest._create_output_item(MagicMock())
        assert result == ['msg1']
