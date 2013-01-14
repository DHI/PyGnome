import datetime
import os

from cornice.resource import resource, view
from pyramid.httpexceptions import HTTPNotFound

from webgnome import util
from webgnome.navigation_tree import NavigationTree
from webgnome.schema import ModelSettingsSchema
from webgnome.views.services.base import BaseResource



@resource(collection_path='/model',
          path='/model/{model_id}',
          renderer='gnome_json',
          description='Create a new model or delete the current model.')
class Model(BaseResource):

    @view(validators=util.valid_model_id)
    def get(self):
        """
        Return a JSON tree representation of the entire model, including movers
        and spills.
        """
        include_movers = self.request.GET.get('include_movers', False)
        include_spills = self.request.GET.get('include_spills', False)
        model_settings = self.request.validated['model'].to_dict(
            include_movers=include_movers, include_spills=include_spills)

        return model_settings
    
    @view(schema=ModelSettingsSchema, validators=util.valid_model_id)
    def put(self):
        """
        Update settings for the current model.
        """
        model = self.request.validated['model']
        model.from_dict(self.request.validated)

        return {
            'success': True
        }   
    
    @view(validators=util.valid_model_id)
    def delete(self):
        """
        Delete the current model.
        """
        self.settings.Model.delete(self.request.matchdict['model_id'])
        message = util.make_message('success', 'Deleted the current model.')
    
        return {
            'success': True,
            'model_id': self.request.matchdict['model_id'],
            'message': message
        }

    @view()
    def collection_post(self):
        """
        Create a new model with default settings.
        """
        model = self.settings.Model.create(
            model_images_dir=self.settings['model_images_dir'])

        message = util.make_message('success', 'Created a new model.')
        self.request.session[self.settings['model_session_key']] = model.id

        return {
            'success': True,
            'model_id': model.id,
            'message': message
        }


@resource(path='/model/{model_id}/tree', renderer='gnome_json',
          description='A Dynatree JSON representation of the current model.')
class ModelTree(BaseResource):

    @view(validators=util.valid_model_id)
    def get(self):
        """
        Return a JSON representation of the current state of the model, to be used
        to create a tree view of the model in the JavaScript application.
        """
        return NavigationTree(self.request.validated['model']).render()
    
    
@resource(path='/model/{model_id}/runner', renderer='gnome_json',
          description='Run the current model.')
class ModelRunner(BaseResource):
    def _get_timestamps(self):
        """
        Get the expected timestamps for a model run.

        TODO: Move into ``gnome.model.Model``?
        """
        timestamps = []
        model = self.request.validated['model']

        # XXX: Why is _num_time_steps a float? Is this ok?
        for step_num in range(int(model._num_time_steps) + 1):
            if step_num == 0:
                dt = model.start_time
            else:
                delta = datetime.timedelta(
                    seconds=step_num * model.time_step)
                dt = model.start_time + delta
            timestamps.append(dt)

        return timestamps

    def _get_next_step(self):
        """
        Generate the next step of the model run and return a dict of metadata
        describing the step, including a URL to an image of particles.
        """
        step = None
        model = self.request.validated['model']

        try:
            curr_step, file_path, timestamp = model.next_image(model.data_dir)
            filename = file_path.split(os.path.sep)[-1]
            image_url = util.get_model_image_url(self.request, model, filename)

            step = {
                'id': curr_step,
                'url': image_url,
                'timestamp': timestamp
            }
        except StopIteration:
            pass

        return step

    @view(validators=util.valid_model_id)
    def post(self):
        """
        Start a run of the user's current model and return a JSON object
        containing the first time step.
        """
        model = self.request.validated['model']
        data = {}

        # TODO: Some of this should probably be in a model method.
        timestamps = self._get_timestamps()
        model.timestamps = timestamps
        model.runtime = util.get_runtime()
        model.rewind()
        model.time_steps = []
        first_step = self._get_next_step()

        model.time_steps.append(first_step)

        data['expected_time_steps'] = timestamps
        data['time_step'] = first_step
        data['background_image'] = util.get_model_image_url(
            self.request, model, 'background_map.png')
        data['map_bounds'] = model.map.map_bounds.tolist()

        return data

    @view(validators=util.valid_model_id)
    def get(self):
        """
        Get the next step in the model run.
        """
        step = self._get_next_step()

        if not step:
            raise HTTPNotFound

        self.request.validated['model'].time_steps.append(step)

        return {
            'time_step': step
        }
