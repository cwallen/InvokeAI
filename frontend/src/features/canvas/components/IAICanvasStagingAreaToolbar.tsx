import {
  background,
  ButtonGroup,
  ChakraProvider,
  Flex,
} from '@chakra-ui/react';
import { CacheProvider } from '@emotion/react';
import { createSelector } from '@reduxjs/toolkit';
import { useAppDispatch, useAppSelector } from 'app/store';
import IAIButton from 'common/components/IAIButton';
import IAIIconButton from 'common/components/IAIIconButton';
import { GroupConfig } from 'konva/lib/Group';
import _ from 'lodash';
import { emotionCache } from 'main';
import { useCallback, useState } from 'react';
import {
  FaArrowLeft,
  FaArrowRight,
  FaCheck,
  FaEye,
  FaEyeSlash,
  FaTrash,
} from 'react-icons/fa';
import { canvasSelector } from 'features/canvas/store/canvasSelectors';
import {
  commitStagingAreaImage,
  discardStagedImages,
  nextStagingAreaImage,
  prevStagingAreaImage,
  setShouldShowStagingImage,
  setShouldShowStagingOutline,
} from 'features/canvas/store/canvasSlice';

const selector = createSelector(
  [canvasSelector],
  (canvas) => {
    const {
      layerState: {
        stagingArea: { images, selectedImageIndex },
      },
      shouldShowStagingOutline,
      shouldShowStagingImage,
    } = canvas;

    return {
      currentStagingAreaImage:
        images.length > 0 ? images[selectedImageIndex] : undefined,
      isOnFirstImage: selectedImageIndex === 0,
      isOnLastImage: selectedImageIndex === images.length - 1,
      shouldShowStagingImage,
      shouldShowStagingOutline,
    };
  },
  {
    memoizeOptions: {
      resultEqualityCheck: _.isEqual,
    },
  }
);

const IAICanvasStagingAreaToolbar = () => {
  const dispatch = useAppDispatch();
  const {
    isOnFirstImage,
    isOnLastImage,
    currentStagingAreaImage,
    shouldShowStagingImage,
  } = useAppSelector(selector);

  const handleMouseOver = useCallback(() => {
    dispatch(setShouldShowStagingOutline(false));
  }, [dispatch]);

  const handleMouseOut = useCallback(() => {
    dispatch(setShouldShowStagingOutline(true));
  }, [dispatch]);

  if (!currentStagingAreaImage) return null;

  return (
    <Flex
      pos={'absolute'}
      bottom={'1rem'}
      w={'100%'}
      align={'center'}
      justify={'center'}
      filter="drop-shadow(0 0.5rem 1rem rgba(0,0,0))"
      onMouseOver={handleMouseOver}
      onMouseOut={handleMouseOut}
    >
      <ButtonGroup isAttached>
        <IAIIconButton
          tooltip="Previous"
          tooltipProps={{ placement: 'bottom' }}
          aria-label="Previous"
          icon={<FaArrowLeft />}
          onClick={() => dispatch(prevStagingAreaImage())}
          data-selected={true}
          isDisabled={isOnFirstImage}
        />
        <IAIIconButton
          tooltip="Next"
          tooltipProps={{ placement: 'bottom' }}
          aria-label="Next"
          icon={<FaArrowRight />}
          onClick={() => dispatch(nextStagingAreaImage())}
          data-selected={true}
          isDisabled={isOnLastImage}
        />
        <IAIIconButton
          tooltip="Accept"
          tooltipProps={{ placement: 'bottom' }}
          aria-label="Accept"
          icon={<FaCheck />}
          onClick={() => dispatch(commitStagingAreaImage())}
          data-selected={true}
        />
        <IAIIconButton
          tooltip="Show/Hide"
          tooltipProps={{ placement: 'bottom' }}
          aria-label="Show/Hide"
          data-alert={!shouldShowStagingImage}
          icon={shouldShowStagingImage ? <FaEye /> : <FaEyeSlash />}
          onClick={() =>
            dispatch(setShouldShowStagingImage(!shouldShowStagingImage))
          }
          data-selected={true}
        />
        <IAIIconButton
          tooltip="Discard All"
          tooltipProps={{ placement: 'bottom' }}
          aria-label="Discard All"
          icon={<FaTrash />}
          onClick={() => dispatch(discardStagedImages())}
          data-selected={true}
          style={{ backgroundColor: 'var(--btn-delete-image)' }}
        />
      </ButtonGroup>
    </Flex>
  );
};

export default IAICanvasStagingAreaToolbar;
