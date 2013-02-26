"""Module providing the ImageStorage class that handles saving
uploaded images to disk."""

import os.path
import shlex
import subprocess
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage


# Command-line invocations of image conversion.
CONVERT_TO_JP2 = 'kdu_compress -i %s -o %s -rate -,4,2.34,1.36,0.797,0.466,0.272,0.159,0.0929,0.0543,0.0317,0.0185 Stiles="{1024,1024}" Cblk="{64,64}" Creversible=no Clevels=5 Corder=RPCL Cmodes=BYPASS'
CONVERT_TO_JP2_LOSSLESS = 'kdu_compress -i "%s" -o "%s" -rate - Creversible=yes Clevels=5 Stiles="{1024,1024}" Cblk="{64,64}" Corder=RPCL'
CONVERT_TO_TIFF = 'convert -compress None %s %s'


class ImageStorage (FileSystemStorage):

    """Storage class for images.

    When an image is saved, the original file is converted into
    JPEG2000 format.

    The conversion process operates as follows:

    * A unique filename is generated for the uploaded image.

    * The uploaded image is saved. This image is likely not in the
      desired format, and so will require conversion, but is
      nonetheless saved at the filename that will be used for the
      converted image.

    * The initial conversion to TIFF (using ImageMagick's convert
      command) saves the new file at
      <real_filename>_1.tif. ImageMagick does not depend on the file
      extension for determining the correct format of the
      to-be-converted image, so it does not matter that it is "convert
      foo.jp2 foo_1.tif" even though foo.jp2 is a PNG, for example.

    * The converted file is converted again, using Kakadu's
      kdu_compress command, with the output file being the original
      path.

    """

    def _save (self, name, content):
        name = super(ImageStorage, self)._save(name, content)
        self._convert_image(name)
        return name

    def _convert_image (self, name):
        """Converts the image file at `name` to the preferred image
        format."""
        full_path = self.path(name)
        dir_name, file_name = os.path.split(full_path)
        file_root, file_ext = os.path.splitext(file_name)
        temp_file = os.path.join(dir_name, '%s_1.tif' % file_root)
        # Convert to a TIFF image. This is a necessary step even
        # though ultimately a JPEG2000 image is wanted, since the
        # conversion to JPEG2000 requires a TIFF for input (that has
        # the .tif extension).
        command = CONVERT_TO_TIFF % (full_path, temp_file)
        self._call_image_conversion(command, full_path)
        command = CONVERT_TO_JP2 % (temp_file, full_path)
        self._call_image_conversion(command, temp_file)
        # Reset permissions (code taken from FileSystemStorage._save).
        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)

    def _call_image_conversion (self, command, input_path):
        """Run the supplied image conversion `command`.

        Tidy up by removing the original image at `input_path`.

        """
        try:
            subprocess.check_call(shlex.split(command.encode('ascii')))
        except subprocess.CalledProcessError, e:
            os.remove(input_path)
            raise IOError('Failed to convert the page image to .jp2: %s' % e)
        finally:
            # Tidy up by deleting the original image, regardless of
            # whether the conversion is successful or not.
            os.remove(input_path)

    def full_base_url (self, name):
        if self.base_url is None:
            raise ValueError('This file is not accessible via a URL.')
        return '%s?FIF=%s' % (self.base_url, name)

    def url (self, name):
        """Returns the URL where the contents of the file referenced
        by `name` can be accessed.

        This is the URL of the image as served by the IIP image
        server.

        """
        return '%s&RST=*&QLT=100&CVT=JPEG' % self.full_base_url(name)


image_storage = ImageStorage(location=settings.IMAGE_SERVER_ROOT,
                             base_url=settings.IMAGE_SERVER_URL)


def get_image_path (instance, filename):
    """Returns the upload path for a page image.

    The path returned is a Unix-style path with forward slashes.

    This filename is entirely independent of the supplied `name`. It
    includes a directory prefix of the first character of the UUID and
    a fixed 'jp2' extension.

    Note that the image that `name` is of is most likely not a JPEG
    2000 image. However, even though we're using a UUID, it's worth
    not futzing about with the possibility of collisions with the
    eventual filename. Also, it's more convenient to always be passing
    around the real filename.

    :param instance: the instance of the model where the ImageField is
      defined
    :type instance: `models.Model`
    :param filename: the filename that was originally given to the file
    :type filename: `str`
    :rtype: `str`

    """
    if instance.id:
        # Reuse the existing filename. Unfortunately,
        # instance.image.name gives the filename of the image being
        # uploaded, so load the original record.
        original = instance._default_manager.get(pk=instance.id)
        image_path = original.image.name
        if not image_path:
            # While the model instance exists, it previously had no
            # image, so generate a new image path.
            image_path = generate_new_image_path()
        else:
            # The original image file must be deleted or else the save
            # will add a suffix to `image_path`.
            original.image.delete(save=False)
    else:
        image_path = generate_new_image_path()
    return image_path

def generate_new_image_path ():
    filename = str(uuid.uuid4())
    directory = filename[0]
    image_path = '%s/%s.jp2' % (directory, filename)
    return image_path
