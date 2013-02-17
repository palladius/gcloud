
#################
# Deploy the gem 'gcloud'

Echoe.new('palladius') do |p|
  p.summary        = "Google Cloud gem. See http://github.com/palladius/gcloud"
  p.description    = "My Google Cloud gem with various utilities. 
  
  More to come
  "
  p.url            = "http://github.com/palladius/palladius"
  p.author         = "Riccardo Carlesso"
  p.email          = "palladiusbonton AT gmail DOT com"
  #  So I can't accidentally ship with without certificate! Yay!
  # See: http://rubydoc.info/gems/echoe/4.6.3/frames
  p.require_signed = true
  p.ignore_pattern = [
    "tmp/*", 
    "tmp/*", #"tmp/*/*", "tmp/*/*/*",
    "private/*",
    ".noheroku",
    '.travis.yml',
  ]
  #p.development_dependencies = [ 'ric' ]
  #p.runtime_dependencies     = [ 'ric', 'sakuric', 'facter' ]
end
