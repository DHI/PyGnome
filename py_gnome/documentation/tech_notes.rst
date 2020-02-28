################
GNOME Tech Notes
################

Assorted technical notes about GNOME and its algorithms and use.

These are often responses to questions from users.


The role of mass in GNOME
=========================

Question from a user:
---------------------

  I am doing an experiment, in which the position of a drifting buoy (3000 kg) is predicted from a known initial position.

  The predicted position is found to be same for an object with different mass. That is :
​
  I took only one splot (as one drifting buoy with 3000 kg) and drove it with ocean currents.  Then i changed the mass as 1 kg and forced the model with currents, again i got the same position only.

  Generally the mass of the object plays a role in drift. But in the above case, i got the same position even after changing the mass of the particle.

Response:
---------

You are correct, changing the mass will not have any effect on the drift. That is because the particles represent an arbitrary division of whatever is being modeled —- it could be 1 gram per particle or 1000kg per particle, depending on the mass released and number of particles used.

  ​I took only one splot (as one drifting buoy with 3000 kg) and drove it with ocean currents.  Then i changed the mass as 1 kg and forced the model with currents, again i got the same position only.

That is expected.

  Generally the mass of the object plays a role in drift.

Well, not really — what effects drift is how it floats in the water. That is, how much of the object is under the water, and how deep, and how much is exposed above the surface to be affected by the wind.

In GNOME, the particles move directly with the surface currents, and are moved by the wind according to the “windage” (sometimes called "leeway") of the particles.

To model a drifting object like a buoy, you will need to have winds, and set an appropriate windage for that buoy. Which is a bit of an art. Ideally, when we do this, we have its position at more than one time so we can calibrate.

There is also literature from the Search and Rescue field about the wind drift factors of various objects in the water.

Oil is generally at the air-water interface, which theoretically results in a “windage” of 3%, which turns out to work pretty well for fresh oil. GNOME defaults to a windage range of 1.0--4.0% which accounts for the tendency of oil to spread in the downwind direction.

Also, there is sub-grid scale circulations not resolved in the models. This is accounted for by the diffusion parameter.

A single object will not diffuse, but it may take a different path depending on these small scale circulations. So it is best to use multiple elements, and apply a random diffusion. The results then are less deterministic, but represent a probability of where the buoy may end up. That is, where the particles are more dense, there is a higher probability that the buoy would be at that location.

As you don’t know the actual windage, you will also want to set a range of windages, accounting for that uncertainty.

Stokes Drift
============

GNOME currently does not include Stokes drift. In a future version, we are likely to add it, but in the meantime:

A number of other oil spill and surface drift models do add a stokes drift component -- but It is challenging to do correctly.

- Stokes drift is the net Eulerian flow integrated over the entire wave in space and time -- in the vertical, it's almost entirely in the trough-crest region. But oil floats -- so it's at or near the surface -- so it's not really moving at the Stokes drift velocity. So if you want to look at wave transport of oil, you need to be thinking about it differently. Here is some work that computes the surface velocity with waves, to get a estimate of the  movement of oil by waves:

http://journals.fcla.edu/jcr/article/view/80162

That was based on a fully non-linear solution to the wave equations and integrated the surface velocity -- something like that would be the "right" way to capture wave transport. Though it is even more complicated -- with white-capping, oil is entrained as droplets under the water -- these are then moved by the orbital velocities of the waves, while rising back to the surface do to buoyancy. This results in a spreading in the downwind direction. GNOME captures this bulk effect with a range of windages, but there has been recent work that has quantified this more carefully.

However: for locally generated wind waves, the waves and wind are moving in the same direction -- so it's really hard to tease out the difference between wave transport and wind transport -- I suspect that the "windage" values we see have a bit of wave transport in them.

When it might matter is when the waves are not locally generated, and more importantly, have been refracted toward shore -- this could provide a mechanism to bring oil ashore without an onshore wind. But: this would only be useful if you had an appropriate wave model driving it -- those are becoming more available, so might be worth including some day, but most folks are modeling the waves from the local winds, so not really capturing this effect at all.

The Stokes drift effect may be more critical for tarballs, which float low in the water, and may not move with the wind as much.

Diffusion
=========

“Diffusion” is a way to capture all the small scale circulations that is not captured in the underlying circulation model. This is often known as “sub-gridscale circulation”. These small eddies, etc, tend to serve to spread things out, or “diffuse” them.

GNOME simulates this effect with a simple random walk algorithm -- it simulates isotropic diffusion, that is the same everywhere. But selection of the diffusion coefficient is a bit of an art.

An appropriate coefficient should represent the level of mixing in the region in question, but also should be scaled to the underlying circulation model that is being used. Diffusion tends to scale with the length scale of a pollutant: A small "blob" will be diffused by small eddies, and simply moved by larger ones. This is known as "Richardson's 4/3 law".

This effect leads to the observation that when there is a pollutant injected at a point source, it begins with a smaller diffusion rate, which increases with time, as the scale of the pollutant "cloud" increases. This appears to be a time-dependent diffusion, but it really a spatial-scale dependent diffusion.

A given circulation model with contain eddies of a certain scale which defines the lower limit of the "diffusion" that is captured in the model.

So when selecting a diffusion parameter in GNOME, the goal is to find a value large enough to capture what is not in the circulation model, but is below the diffusion inherent in velocity field in the model. In theory, that could be calculated from the grid size of the model, but in practice, there is not a direct relationship between the grid size than the scale of circulation captured.

In practice, in a real oil spill, if there are observations of the oil transport, we will adjust the diffusion to match the amount of spreading seem in the field. Before there are observations, we use a coefficient that matches, to some extent, then scale of the region the spill occurs: 1X10^5 cm^2/s works fairly well in most coastal zones, and smaller numbers are more appropriate for Bays and Estuaries.

But for response, the goal is to capture where, and how far the oil might travel, so it is more conservative to use a larger diffusion. But this does lead to over estimation of the spreading, which may lead to under-estimating the surface concentration. For use other than response, smaller diffusion coefficients may be more appropriate.

In the end, without observations to calibrate to -- diffusion needs to be selected such that it fits the scale and complexity of the region being modeled -- large enough to spread, but small enough to not "wash out" the details captured in the underlying circulation model.
















