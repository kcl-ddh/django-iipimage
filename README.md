django-iipimage
===============

Django app to provide integration with IIPImage server.

To use, add iipimage to INSTALLED_APPS and appropriate values for the
following two variables in settings.py:

* IMAGE_SERVER_URL - the URL of the IIPImage server script
* IMAGE_SERVER_ROOT - the path to where the images are to be stored

In the model definition, use something along the following lines:

    import iipimage.fields
    import iipimage.storage

    class Image (models.Model):

        image = iipimage.fields.ImageField(
            storage=iipimage.storage.image_storage,
            upload_to=iipimage.storage.get_image_path)

`iipimage.fields.ImageField` supports the `height_field` and
`width_field` arguments, and has a `thumbnail_url` method that returns
a URL for a thumbnail at the specified height and/or width.
