import numpy as np
from PIL import Image
import logging, shutil, asyncio, os, time, re

# Configure logging for better error visibility
logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")


async def convert_image_to_ascii(
    filepath: str,
    characters: str,
    target_width: int,
    terminal_max_height: int,
) -> list[str] | None:
    """
    Converts an image to ASCII art, maintaining aspect ratio and fitting within terminal height.

    Args:
        filepath: Path to the image file.
        characters: A string of characters ordered from darkest to lightest.
        target_width: Desired width of ASCII art in characters.
        terminal_max_height: Maximum allowed height in characters (from terminal size).
        char_aspect_ratio: The width-to-height ratio of a single character in the terminal.

    Returns:
        A list of strings representing the ASCII art, or None on failure.
    """
    try:
        img = Image.open(filepath)
    except Exception as e:
        logging.error(f"Failed to open image file '{filepath}': {e}")
        return None

    original_width, original_height = img.size

    ar = original_height / original_width
    new_height = int(ar * target_width * 0.5)
    while new_height > terminal_max_height:
        target_width -= 1
        new_height = int(ar * target_width * 0.5)

    # If the calculated height is too small (e.g., image is very wide),
    # ensure a minimum height to avoid zero or tiny output.
    if new_height <= 0:
        logging.warning(
            f"Calculated ASCII art height for '{filepath}' is too small ({new_height}). Setting minimum height to 1."
        )
        new_height = 1  # Ensures at least one line of output

    # Resize image to the calculated ASCII dimensions
    # Using Image.LANCZOS for high-quality downsampling
    img = img.resize((target_width, new_height), Image.LANCZOS)
    img = img.convert("L")  # Convert to grayscale

    # Map pixel intensity to character index
    pixel_values = np.array(img)
    num_chars = len(characters)
    # Scale pixel values (0-255) to the range of character indices (0 to num_chars-1)
    scaled_pixels = (pixel_values / 255 * (num_chars - 1)).astype(int)

    # Build ASCII art lines
    ascii_art = ["".join(characters[pixel] for pixel in row) for row in scaled_pixels]
    return ascii_art


async def convert_gif_to_image_frames(
    gif_path: str, output_dir: str, frame_prefix: str = "frame"
) -> list[str]:
    """
    Extracts frames from a GIF using ffmpeg and saves them as image files.

    Args:
        gif_path: Path to the GIF file.
        output_dir: Directory to save the extracted frames.
        frame_prefix: Prefix for the frame filenames (e.g., 'frame_001.png').

    Returns:
        A sorted list of paths to the extracted image frames.
    """
    os.makedirs(output_dir, exist_ok=True)
    frame_name_pattern = os.path.join(
        output_dir, f"{frame_prefix}_%04d.png"
    )  # %04d for 4-digit frame numbers

    command = [
        "ffmpeg",
        "-hide_banner",  # Hide ffmpeg startup banner
        "-i",
        gif_path,  # Input GIF file
        frame_name_pattern,  # Output pattern for frames
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,  # Suppress ffmpeg output
        stderr=asyncio.subprocess.DEVNULL,  # Suppress ffmpeg errors to console
    )

    # Wait for ffmpeg to complete
    await process.wait()

    if process.returncode != 0:
        logging.error(
            f"FFmpeg failed to extract frames from {gif_path}. Return code: {process.returncode}"
        )
        return []

    # Get sorted list of extracted files
    files = [
        os.path.join(output_dir, p)
        for p in os.listdir(output_dir)
        if p.startswith(frame_prefix)
    ]
    files.sort(
        key=lambda x: int(re.search(r"(\d+)", x).group(0))
    )  # Sort by frame number
    return files


async def print_ascii_art(art_lines: list[str], center: bool = False):
    """
    Clears the terminal and prints the ASCII art.

    Args:
        art_lines: A list of strings, where each string is a line of ASCII art.
        center: If True, centers each line of ASCII art in the terminal.
    """
    # Use 'cls' for Windows, 'clear' for Unix/Linux/macOS
    os.system("cls" if os.name == "nt" else "clear")

    terminal_width = shutil.get_terminal_size((80, 20)).columns  # Fallback to 80, 20

    # Join lines and optionally center them
    gen_art = "\n".join(
        line.center(terminal_width) if center else line for line in art_lines
    )
    print(gen_art)


async def main():
    """Main function to run the ASCII art GIF animation."""
    # Characters ordered from darkest to lightest (more characters give more detail)
    charset = r"@%#*+=-:. "
    gif_path = "gifs/gif.gif"  # Path to your GIF file
    temp_dir = "temp_gif_frames"  # Directory to store extracted frames

    # Get terminal dimensions
    terminal_size = shutil.get_terminal_size(fallback=(80, 20))
    # Leave some padding for the prompt and general buffer
    ascii_width = terminal_size.columns - 5
    ascii_height_limit = terminal_size.lines - 5

    print(f"Extracting frames from '{gif_path}'...")
    image_paths = await convert_gif_to_image_frames(gif_path, temp_dir)

    if not image_paths:
        logging.error("No image frames extracted. Exiting.")
        return

    print("Converting image frames to ASCII art...")
    all_ascii_frames = []
    for i, image_path in enumerate(image_paths):
        # The character aspect ratio (0.45) is passed here
        ascii_frame = await convert_image_to_ascii(
            image_path,
            characters=charset,
            target_width=ascii_width,
            terminal_max_height=ascii_height_limit,
        )
        if ascii_frame:
            all_ascii_frames.append(ascii_frame)
        else:
            logging.warning(f"Skipping frame {i+1} due to conversion failure.")

    if not all_ascii_frames:
        logging.error("No ASCII frames generated. Exiting.")
        return

    print(
        "Press Enter to start/restart animation. Type 'q' to quit. You can also type a number (e.g., '3') to repeat the animation that many times."
    )

    while True:
        try:
            user_input = input("> ").strip().lower()
            if user_input == "q":
                break

            times_to_repeat = 1  # Default to 1 loop
            match = re.search(r"(\d+)", user_input)
            if match:
                times_to_repeat = int(match.group(0))

            for _ in range(times_to_repeat):
                for frame_art in all_ascii_frames:
                    await print_ascii_art(frame_art)
                    await asyncio.sleep(
                        0.04
                    )  # Adjust for desired animation speed (25 frames per second)
        except KeyboardInterrupt:
            print("\nAnimation interrupted.")
            break
        except Exception as e:
            logging.error(f"An unexpected error occurred during animation loop: {e}")
            break


if __name__ == "__main__":
    temp_directory = "temp_gif_frames"
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Application terminated due to an unhandled error: {e}")
    finally:
        # Clean up temporary directory on exit
        if os.path.exists(temp_directory):
            print(f"Cleaning up temporary directory: {temp_directory}")
            shutil.rmtree(temp_directory)
