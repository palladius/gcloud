
#################
# Deploy the gem 'gcloud'
gemnames = %w{ gcloud googlecloud }

gemnames.each do |gemname|
  Echoe.new(gemname) do |p|
    p.summary        = "Google Cloud gem. See http://github.com/palladius/gcloud"
    p.description    = "My Google Cloud gem ('#{gemname}') with various utilities. 
  
    It deploys gcutil, gsutil, and more.
    "
    p.url            = "http://github.com/palladius/gcloud"
    p.author         = "Riccardo Carlesso"
    p.email          = "palladiusbonton AT gmail DOT com"
    p.path           = [ 'bin/', 'packages/gcutil']
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
end